#include "py/runtime.h"
#include "py/misc.h"
#include "app_i2c.h"

#if BEIIS_APP_IO_ENABLED

static mp_obj_t mod_appio_try_send(mp_obj_t instance_obj, mp_obj_t channel_obj, mp_obj_t data_obj) {
    int instance = mp_obj_get_int(instance_obj);
    int channel = mp_obj_get_int(channel_obj);
    mp_buffer_info_t data;
    mp_get_buffer_raise(data_obj, &data, MP_BUFFER_READ);
    if (instance < 0 || instance > 255 || channel < 0 || channel > 255) {
        mp_raise_ValueError(MP_ERROR_TEXT("invalid instance/channel"));
    }
    int result = beiis_app_try_send((uint8_t)instance, (uint8_t)channel, data.buf, data.len);
    if (result < 0) {
        mp_raise_ValueError(MP_ERROR_TEXT("invalid application frame"));
    }
    return mp_obj_new_bool(result != 0);
}
static MP_DEFINE_CONST_FUN_OBJ_3(mod_appio_try_send_obj, mod_appio_try_send);

static mp_obj_t mod_appio_recv(void) {
    uint8_t channel;
    size_t len;
    int ready = beiis_app_rx_peek(&channel, &len);
    if (ready == 0) {
        return mp_const_none;
    }
    if (ready < 0) {
        mp_raise_ValueError(MP_ERROR_TEXT("invalid application frame"));
    }

    size_t alloc_len = len ? len : 1;
    uint8_t *buf = m_new(uint8_t, alloc_len);
    size_t received = 0;
    int result = beiis_app_recv(&channel, buf, len, &received);
    if (result <= 0) {
        m_del(uint8_t, buf, alloc_len);
        if (result == 0) {
            return mp_const_none;
        }
        mp_raise_ValueError(MP_ERROR_TEXT("application frame receive failed"));
    }

    mp_obj_t tuple[2] = {
        mp_obj_new_int(channel),
        mp_obj_new_bytes(buf, received),
    };
    m_del(uint8_t, buf, alloc_len);
    return mp_obj_new_tuple(2, tuple);
}
static MP_DEFINE_CONST_FUN_OBJ_0(mod_appio_recv_obj, mod_appio_recv);

static mp_obj_t mod_appio_reset(void) {
    beiis_app_i2c_init();
    return mp_const_none;
}
static MP_DEFINE_CONST_FUN_OBJ_0(mod_appio_reset_obj, mod_appio_reset);

static mp_obj_t mod_appio_active_instance(void) {
    return mp_obj_new_int(beiis_app_active_instance());
}
static MP_DEFINE_CONST_FUN_OBJ_0(mod_appio_active_instance_obj, mod_appio_active_instance);

static mp_obj_t mod_appio_set_active_instance(mp_obj_t instance_obj) {
    int instance = mp_obj_get_int(instance_obj);
    if (instance < 0 || instance >= BEIIS_APP_MAX_INSTANCES) {
        mp_raise_ValueError(MP_ERROR_TEXT("instance must be 0..7"));
    }
    if (beiis_app_set_active_instance((uint8_t)instance) != 0) {
        mp_raise_ValueError(MP_ERROR_TEXT("invalid active instance"));
    }
    return mp_const_none;
}
static MP_DEFINE_CONST_FUN_OBJ_1(mod_appio_set_active_instance_obj, mod_appio_set_active_instance);

static const mp_rom_map_elem_t globals_table[] = {
    {MP_ROM_QSTR(MP_QSTR___name__), MP_ROM_QSTR(MP_QSTR_appio)},
    {MP_ROM_QSTR(MP_QSTR_try_send), MP_ROM_PTR(&mod_appio_try_send_obj)},
    {MP_ROM_QSTR(MP_QSTR_recv), MP_ROM_PTR(&mod_appio_recv_obj)},
    {MP_ROM_QSTR(MP_QSTR_reset), MP_ROM_PTR(&mod_appio_reset_obj)},
    {MP_ROM_QSTR(MP_QSTR_active_instance), MP_ROM_PTR(&mod_appio_active_instance_obj)},
    {MP_ROM_QSTR(MP_QSTR_set_active_instance), MP_ROM_PTR(&mod_appio_set_active_instance_obj)},
    {MP_ROM_QSTR(MP_QSTR_MAX_CHANNELS), MP_ROM_INT(BEIIS_APP_USER_CHANNELS)},
    {MP_ROM_QSTR(MP_QSTR_MAX_INSTANCES), MP_ROM_INT(BEIIS_APP_MAX_INSTANCES)},
    {MP_ROM_QSTR(MP_QSTR_MAX_PAYLOAD), MP_ROM_INT(BEIIS_APP_MAX_PAYLOAD)},
    {MP_ROM_QSTR(MP_QSTR_MGMT_CHANNEL), MP_ROM_INT(BEIIS_APP_MGMT_CHANNEL)},
};
static MP_DEFINE_CONST_DICT(globals, globals_table);

const mp_obj_module_t appio_module = {
    .base = {&mp_type_module},
    .globals = (mp_obj_dict_t *)&globals,
};
MP_REGISTER_MODULE(MP_QSTR_appio, appio_module);

#endif
