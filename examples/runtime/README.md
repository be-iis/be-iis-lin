# Runtime examples

These examples use the normal production path:

```text
application -> Unix SOCK_SEQPACKET -> beiis-lind -> STM32 runtime
```

They do not open the HAT I2C device directly.

Prerequisite:

```sh
. .venv/bin/activate
beiis-lind
```

For a development daemon on a temporary socket:

```sh
beiis-lind --socket /tmp/beiis-lin.sock --lock-file /tmp/beiis-lind.lock
```

Pass `--socket /tmp/beiis-lin.sock` to the Python examples and installer, or
pass `/tmp/beiis-lin.sock` as the first argument to the C example.

The standard runtime layout must be installed with:

```sh
python scripts/install-standard-runtime.py
```

## Python LIN example

Show native PING through the master query pair:

```sh
python examples/runtime/python_basic.py master-ping
```

Master publishes a frame:

```sh
python examples/runtime/python_basic.py master-send 0x12 11223344
```

Master requests four bytes:

```sh
python examples/runtime/python_basic.py master-request 0x22 4
```

Configure LIN2 as slave responder:

```sh
python examples/runtime/python_basic.py slave-set 0x22 11223344
```

Disable the response:

```sh
python examples/runtime/python_basic.py slave-clear
```

Configure slave receive:

```sh
python examples/runtime/python_basic.py slave-rx-set 0x12 8
python examples/runtime/python_basic.py slave-rx-recv
```

Logging status:

```sh
python examples/runtime/python_basic.py logging-status
```

The logging status currently reports passive RX as unsupported.

## C socket example

Compile:

```sh
cc -O2 -Wall -Wextra examples/runtime/c_basic.c -o /tmp/beiis-runtime-c
```

Run:

```sh
/tmp/beiis-runtime-c
```

Optional custom socket path:

```sh
/tmp/beiis-runtime-c /tmp/beiis-lin.sock
```

The C example deliberately uses no JSON library. It demonstrates the
`SOCK_SEQPACKET` transport and a master native PING. Production applications
should use a real JSON parser.

## Custom query example

Install the example worker and a new query pair into free slots:

```sh
python examples/runtime/install_custom_query.py
```

Then:

```sh
python examples/runtime/custom_query_client.py "hello world"
```

Expected reply:

```text
reply:HELLO WORLD
```

This example reuses the standard `query.py`; only the middle worker is custom.
