import asyncio
import binascii
import json
import os
import sys

import appio

MAX_INSTANCES = 8
MAX_CHANNELS = 32
MGMT_CHANNEL = 0xFF
ROOT = "/flash/beiis"
APP_DIR = ROOT + "/apps"
CONFIG_PATH = ROOT + "/instances.json"
CONFIG_VERSION = 1
RUNTIME_API_VERSION = 1
MAILBOX_DEPTH = 16
MAX_APP_SIZE = 64 * 1024


def _valid_name(value):
    if not isinstance(value, str) or not value or len(value) > 31:
        return False
    for ch in value:
        if not (("a" <= ch <= "z") or ("A" <= ch <= "Z") or ("0" <= ch <= "9") or ch == "_"):
            return False
    return True


def _ensure_dir(path):
    try:
        os.mkdir(path)
    except OSError:
        pass


def _write_config(config):
    tmp = CONFIG_PATH + ".tmp"
    with open(tmp, "w") as f:
        f.write(json.dumps(config))
        f.flush()
    try:
        os.remove(CONFIG_PATH)
    except OSError:
        pass
    os.rename(tmp, CONFIG_PATH)


def _ensure_storage():
    _ensure_dir(ROOT)
    _ensure_dir(APP_DIR)
    if APP_DIR not in sys.path:
        sys.path.append(APP_DIR)
    try:
        os.stat(CONFIG_PATH)
    except OSError:
        _write_config({"version": CONFIG_VERSION, "instances": []})


def _load_config():
    _ensure_storage()
    try:
        with open(CONFIG_PATH, "r") as f:
            config = json.loads(f.read())
    except Exception:
        config = {"version": CONFIG_VERSION, "instances": []}
    if config.get("version") != CONFIG_VERSION:
        raise ValueError("unsupported app config version")
    instances = config.get("instances")
    if not isinstance(instances, list) or len(instances) > MAX_INSTANCES:
        raise ValueError("invalid instance configuration")
    return config


def _app_path(app):
    if not _valid_name(app):
        raise ValueError("invalid app name")
    return APP_DIR + "/" + app + ".py"


def _installed_apps():
    _ensure_storage()
    out = []
    for name in os.listdir(APP_DIR):
        if name.endswith(".py") and _valid_name(name[:-3]):
            out.append(name[:-3])
    out.sort()
    return out


class Mailbox:
    def __init__(self, depth=MAILBOX_DEPTH):
        self.depth = depth
        self.items = []
        self.event = asyncio.Event()
        self.dropped = 0

    def put_nowait(self, item):
        if len(self.items) >= self.depth:
            self.dropped += 1
            return False
        self.items.append(item)
        self.event.set()
        return True

    async def get(self):
        while not self.items:
            self.event.clear()
            await self.event.wait()
        item = self.items.pop(0)
        if self.items:
            self.event.set()
        return item


class AppContext:
    def __init__(self, manager, spec, mailbox):
        self._manager = manager
        self._mailbox = mailbox
        self.name = spec["name"]
        self.app = spec["app"]
        self.config = spec.get("config") or {}
        self.channels = tuple(spec.get("channels") or ())
        self.resources = tuple(spec.get("resources") or ())
        self.slot = int(spec["slot"])
        self.tap = bool(spec.get("tap", False))
        self.api_version = RUNTIME_API_VERSION

    async def recv(self):
        """Return (source, channel, payload). Source is 'host' or an instance name."""
        return await self._mailbox.get()

    async def send_host(self, channel, payload):
        channel = int(channel)
        if channel < 0 or channel >= MAX_CHANNELS:
            raise ValueError("channel must be 0..31")
        payload = bytes(payload)
        while not appio.try_send(self.slot, channel, payload):
            await asyncio.sleep_ms(1)

    def send_to(self, instance, payload, channel=0):
        return self._manager.send_to(self.name, instance, int(channel), bytes(payload))

    def publish(self, channel, payload):
        return self._manager.publish(self.name, int(channel), bytes(payload))


class Runtime:
    def __init__(self):
        self.config = _load_config()
        self.running = False
        self.states = {}
        self._install = None
        self.resources = {}
        self._assign_slots()

    def _assign_slots(self):
        used = set()
        changed = False
        for spec in self.config["instances"]:
            slot = spec.get("slot")
            if isinstance(slot, int) and 0 <= slot < MAX_INSTANCES and slot not in used:
                used.add(slot)
                continue
            slot = 0
            while slot in used:
                slot += 1
            if slot >= MAX_INSTANCES:
                raise ValueError("no free instance slot")
            spec["slot"] = slot
            used.add(slot)
            changed = True
        if changed:
            self._save()

    def _allocate_slot(self):
        used = {int(spec["slot"]) for spec in self.config["instances"]}
        for slot in range(MAX_INSTANCES):
            if slot not in used:
                return slot
        raise ValueError("no free instance slot")

    def _find_spec(self, name):
        for spec in self.config["instances"]:
            if spec.get("name") == name:
                return spec
        return None

    def _save(self):
        _write_config(self.config)

    def _validate_spec(self, spec):
        name = spec.get("name")
        app = spec.get("app")
        channels = spec.get("channels") or []
        if not _valid_name(name):
            raise ValueError("invalid instance name")
        if not _valid_name(app):
            raise ValueError("invalid app name")
        if len(channels) > MAX_CHANNELS:
            raise ValueError("too many channels")
        seen = set()
        clean = []
        for value in channels:
            channel = int(value)
            if channel < 0 or channel >= MAX_CHANNELS:
                raise ValueError("channel must be 0..31")
            if channel not in seen:
                clean.append(channel)
                seen.add(channel)
        spec["channels"] = clean
        slot = int(spec.get("slot", -1))
        if slot < 0 or slot >= MAX_INSTANCES:
            raise ValueError("instance slot must be 0..7")
        spec["slot"] = slot
        spec["tap"] = bool(spec.get("tap", False))
        spec["autostart"] = bool(spec.get("autostart", False))
        if not isinstance(spec.get("config", {}), dict):
            raise ValueError("config must be an object")
        resources = spec.get("resources") or []
        clean_resources = []
        for resource in resources:
            if not _valid_name(resource):
                raise ValueError("invalid resource name")
            if resource not in clean_resources:
                clean_resources.append(resource)
        spec["resources"] = clean_resources

    def add_instance(self, name, app, channels=None, config=None, autostart=False, resources=None, tap=False):
        if len(self.config["instances"]) >= MAX_INSTANCES:
            raise ValueError("maximum 8 instances")
        if self._find_spec(name) is not None:
            raise ValueError("instance already exists")
        os.stat(_app_path(app))
        spec = {
            "name": name,
            "app": app,
            "slot": self._allocate_slot(),
            "tap": bool(tap),
            "channels": list(channels or []),
            "config": config or {},
            "autostart": bool(autostart),
            "resources": list(resources or []),
        }
        self._validate_spec(spec)
        self.config["instances"].append(spec)
        self._save()
        return dict(spec)

    async def remove_instance(self, name):
        spec = self._find_spec(name)
        if spec is None:
            raise ValueError("unknown instance")
        await self.stop_instance(name)
        self.config["instances"].remove(spec)
        self.states.pop(name, None)
        self._save()

    def set_autostart(self, name, enabled):
        spec = self._find_spec(name)
        if spec is None:
            raise ValueError("unknown instance")
        spec["autostart"] = bool(enabled)
        self._save()
        return spec["autostart"]

    def configure_instance(self, name, channels=None, config=None, resources=None, tap=None):
        spec = self._find_spec(name)
        if spec is None:
            raise ValueError("unknown instance")
        state = self.states.get(name) or {}
        if state.get("state") == "running":
            raise ValueError("stop instance before reconfiguring")
        if channels is not None:
            spec["channels"] = list(channels)
        if config is not None:
            spec["config"] = config
        if resources is not None:
            spec["resources"] = list(resources)
        if tap is not None:
            spec["tap"] = bool(tap)
        self._validate_spec(spec)
        self._save()
        return dict(spec)

    async def _run_instance(self, spec, mailbox):
        name = spec["name"]
        state = self.states[name]
        try:
            app_name = spec["app"]
            module = sys.modules.get(app_name)
            if module is None:
                module = __import__(app_name)
            required_api = getattr(module, "BEIIS_API", RUNTIME_API_VERSION)
            if required_api != RUNTIME_API_VERSION:
                raise ValueError("unsupported app API version")
            entry = getattr(module, "main", None)
            if entry is None:
                raise ValueError("app must define main(ctx)")
            ctx = AppContext(self, spec, mailbox)
            state["state"] = "running"
            result = entry(ctx)
            if result is not None:
                await result
            state["state"] = "stopped"
        except asyncio.CancelledError:
            state["state"] = "stopped"
            raise
        except Exception as exc:
            state["state"] = "crashed"
            state["error"] = repr(exc)
        finally:
            state["task"] = None
            self._release_resources(name)

    def _claim_resources(self, spec):
        for resource in spec.get("resources", ()):
            owner = self.resources.get(resource)
            if owner is not None and owner != spec["name"]:
                raise ValueError("resource %s is owned by %s" % (resource, owner))
        for resource in spec.get("resources", ()):
            self.resources[resource] = spec["name"]

    def _release_resources(self, name):
        for resource, owner in list(self.resources.items()):
            if owner == name:
                del self.resources[resource]

    async def start_instance(self, name):
        spec = self._find_spec(name)
        if spec is None:
            raise ValueError("unknown instance")
        state = self.states.get(name)
        if state is not None and state.get("state") == "running":
            return
        self._claim_resources(spec)
        mailbox = Mailbox()
        state = {"state": "starting", "error": None, "mailbox": mailbox, "task": None}
        self.states[name] = state
        state["task"] = asyncio.create_task(self._run_instance(spec, mailbox))
        await asyncio.sleep_ms(0)

    async def stop_instance(self, name):
        state = self.states.get(name)
        if state is None:
            return
        task = state.get("task")
        if task is not None:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
            except Exception:
                pass
        state["task"] = None
        state["state"] = "stopped"
        self._release_resources(name)

    async def restart_instance(self, name):
        spec = self._find_spec(name)
        if spec is None:
            raise ValueError("unknown instance")
        await self.stop_instance(name)
        app = spec["app"]
        if app in sys.modules:
            del sys.modules[app]
        await self.start_instance(name)

    def send_to(self, source, target, channel, payload):
        if channel < 0 or channel >= MAX_CHANNELS:
            raise ValueError("channel must be 0..31")
        state = self.states.get(target)
        if state is None or state.get("state") != "running":
            return False
        return state["mailbox"].put_nowait((source, channel, payload))

    def publish(self, source, channel, payload):
        if channel < 0 or channel >= MAX_CHANNELS:
            raise ValueError("channel must be 0..31")
        delivered = 0
        for spec in self.config["instances"]:
            if spec["name"] == source or channel not in spec.get("channels", ()):
                continue
            if self.send_to(source, spec["name"], channel, payload):
                delivered += 1
        return delivered

    def _route_host(self, channel, payload):
        active_slot = appio.active_instance()
        active = None
        for spec in self.config["instances"]:
            if int(spec["slot"]) == active_slot:
                active = spec
                break

        if active is None:
            return 0
        active_state = self.states.get(active["name"]) or {}
        if active_state.get("state") != "running":
            return 0

        delivered = 1 if self.send_to("host", active["name"], channel, payload) else 0

        # Taps get a copy; they never consume the owner's message. An empty
        # channel list means tap all user channels, otherwise it is a filter.
        for spec in self.config["instances"]:
            if spec["name"] == active["name"] or not spec.get("tap", False):
                continue
            channels = spec.get("channels") or []
            if channels and channel not in channels:
                continue
            if self.send_to("host", spec["name"], channel, payload):
                delivered += 1
        return delivered

    def status(self):
        result = []
        for spec in self.config["instances"]:
            state = self.states.get(spec["name"]) or {}
            mailbox = state.get("mailbox")
            result.append({
                "name": spec["name"],
                "app": spec["app"],
                "slot": int(spec["slot"]),
                "tap": bool(spec.get("tap", False)),
                "active": int(spec["slot"]) == appio.active_instance(),
                "channels": list(spec.get("channels") or []),
                "resources": list(spec.get("resources") or []),
                "autostart": bool(spec.get("autostart", False)),
                "state": state.get("state", "stopped"),
                "error": state.get("error"),
                "dropped": mailbox.dropped if mailbox is not None else 0,
            })
        return result

    def _install_begin(self, app, size):
        size = int(size)
        if size < 0 or size > MAX_APP_SIZE:
            raise ValueError("app size must be 0..65536 bytes")
        path = _app_path(app)
        tmp = path + ".tmp"
        with open(tmp, "wb"):
            pass
        self._install = {"app": app, "path": path, "tmp": tmp, "size": size, "written": 0}
        return {"app": app, "size": size}

    def _install_chunk(self, app, data_hex):
        if self._install is None or self._install["app"] != app:
            raise ValueError("no matching install in progress")
        data = binascii.unhexlify(data_hex)
        with open(self._install["tmp"], "ab") as f:
            f.write(data)
        self._install["written"] += len(data)
        if self._install["written"] > self._install["size"]:
            raise ValueError("install exceeds declared size")
        return {"written": self._install["written"]}

    def _install_commit(self, app, crc32):
        if self._install is None or self._install["app"] != app:
            raise ValueError("no matching install in progress")
        item = self._install
        if item["written"] != item["size"]:
            raise ValueError("install size mismatch")
        crc = 0
        with open(item["tmp"], "rb") as f:
            while True:
                block = f.read(256)
                if not block:
                    break
                crc = binascii.crc32(block, crc)
        crc &= 0xFFFFFFFF
        expected = int(crc32) & 0xFFFFFFFF
        if crc != expected:
            raise ValueError("install CRC mismatch")
        try:
            os.remove(item["path"])
        except OSError:
            pass
        os.rename(item["tmp"], item["path"])
        if app in sys.modules:
            del sys.modules[app]
        self._install = None
        return {"app": app, "crc32": crc}

    def _remove_app(self, app):
        for spec in self.config["instances"]:
            if spec["app"] == app:
                raise ValueError("app is still referenced by an instance")
        os.remove(_app_path(app))
        if app in sys.modules:
            del sys.modules[app]

    async def _control(self, request):
        op = request.get("op")
        args = request.get("args") or {}
        if op == "info":
            return {
                "runtime": 1,
                "app_api": RUNTIME_API_VERSION,
                "max_instances": MAX_INSTANCES,
                "max_channels": MAX_CHANNELS,
                "max_app_size": MAX_APP_SIZE,
                "active_instance": appio.active_instance(),
                "apps": _installed_apps(),
                "instances": self.status(),
            }
        if op == "app_list":
            return _installed_apps()
        if op == "install_begin":
            return self._install_begin(args["app"], args["size"])
        if op == "install_chunk":
            return self._install_chunk(args["app"], args["data"])
        if op == "install_commit":
            return self._install_commit(args["app"], args["crc32"])
        if op == "app_remove":
            self._remove_app(args["app"])
            return True
        if op == "instance_add":
            return self.add_instance(
                args["name"], args["app"], args.get("channels"), args.get("config"), args.get("autostart", False), args.get("resources"), args.get("tap", False)
            )
        if op == "instance_remove":
            await self.remove_instance(args["name"])
            return True
        if op == "instance_configure":
            return self.configure_instance(args["name"], args.get("channels"), args.get("config"), args.get("resources"), args.get("tap"))
        if op == "instance_list":
            return self.status()
        if op == "active_instance":
            if "slot" in args:
                appio.set_active_instance(int(args["slot"]))
            return appio.active_instance()
        if op == "start":
            await self.start_instance(args["name"])
            return True
        if op == "stop":
            await self.stop_instance(args["name"])
            return True
        if op == "restart":
            await self.restart_instance(args["name"])
            return True
        if op == "autostart":
            return self.set_autostart(args["name"], args["enabled"])
        if op == "runtime_stop":
            self.running = False
            return True
        raise ValueError("unknown runtime operation")

    async def _reply(self, request_id, ok, result=None, error=None):
        message = {"id": request_id, "ok": ok}
        if ok:
            message["result"] = result
        else:
            message["error"] = error
        data = json.dumps(message).encode()
        while not appio.try_send(0xff, MGMT_CHANNEL, data):
            await asyncio.sleep_ms(1)

    async def _handle_management(self, payload):
        request_id = 0
        try:
            request = json.loads(payload.decode())
            request_id = int(request.get("id", 0))
            result = await self._control(request)
            await self._reply(request_id, True, result=result)
        except Exception as exc:
            await self._reply(request_id, False, error=repr(exc))

    async def _dispatcher(self):
        while self.running:
            frame = appio.recv()
            if frame is None:
                await asyncio.sleep_ms(1)
                continue
            channel, payload = frame
            if channel == MGMT_CHANNEL:
                await self._handle_management(payload)
            elif channel < MAX_CHANNELS:
                self._route_host(channel, payload)

    async def run(self):
        self.running = True
        try:
            for spec in self.config["instances"]:
                self._validate_spec(spec)
                if spec.get("autostart"):
                    await self.start_instance(spec["name"])

            # Keep the management/data dispatcher in the main runtime task.
            # If it fails, propagate the exception instead of leaving a
            # zombie runtime that still owns the MicroPython interpreter.
            await self._dispatcher()
        finally:
            for spec in self.config["instances"]:
                await self.stop_instance(spec["name"])


def boot_if_needed():
    config = _load_config()
    for spec in config["instances"]:
        if spec.get("autostart"):
            asyncio.run(Runtime().run())
            return True
    return False
