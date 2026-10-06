#include <string.h>
#include "py/runtime.h"
#include "lin.h"

#if BEIIS_LIN_MODULE_ENABLED

static mp_obj_t mod_lin_init(mp_obj_t channel_obj,mp_obj_t baud_obj) {
    uint8_t channel=(uint8_t)mp_obj_get_int(channel_obj);
    int r=lin_init(channel,(uint32_t)mp_obj_get_int(baud_obj));
    if(r!=LIN_OK) mp_raise_OSError(-r);
    return mp_const_none;
}
static MP_DEFINE_CONST_FUN_OBJ_2(mod_lin_init_obj,mod_lin_init);

static mp_obj_t mod_lin_send(size_t n,const mp_obj_t *a) {
    uint8_t channel=(uint8_t)mp_obj_get_int(a[0]);
    lin_frame_t f={0};
    f.id=(uint8_t)mp_obj_get_int(a[1]);
    mp_buffer_info_t b;
    mp_get_buffer_raise(a[2],&b,MP_BUFFER_READ);
    if(b.len>8) mp_raise_ValueError(MP_ERROR_TEXT("LIN data > 8 bytes"));
    f.len=(uint8_t)b.len;
    memcpy(f.data,b.buf,b.len);
    lin_checksum_mode_t m=(n>3&&!mp_obj_is_true(a[3]))?LIN_CHECKSUM_CLASSIC:LIN_CHECKSUM_ENHANCED;
    int r=lin_master_send(channel,&f,m,100);
    if(r!=LIN_OK) mp_raise_OSError(-r);
    return mp_const_none;
}
static MP_DEFINE_CONST_FUN_OBJ_VAR_BETWEEN(mod_lin_send_obj,3,4,mod_lin_send);

static mp_obj_t mod_lin_request(size_t n,const mp_obj_t *a) {
    uint8_t channel=(uint8_t)mp_obj_get_int(a[0]);
    uint8_t id=(uint8_t)mp_obj_get_int(a[1]);
    uint8_t len=(uint8_t)mp_obj_get_int(a[2]);
    lin_checksum_mode_t m=(n>3&&!mp_obj_is_true(a[3]))?LIN_CHECKSUM_CLASSIC:LIN_CHECKSUM_ENHANCED;
    lin_frame_t f;
    int r=lin_master_request(channel,id,len,m,&f,100);
    if(r!=LIN_OK) mp_raise_OSError(-r);
    return mp_obj_new_bytes(f.data,f.len);
}
static MP_DEFINE_CONST_FUN_OBJ_VAR_BETWEEN(mod_lin_request_obj,3,4,mod_lin_request);


static mp_obj_t mod_lin_request_raw(mp_obj_t channel_obj,mp_obj_t id_obj,mp_obj_t len_obj) {
    uint8_t channel=(uint8_t)mp_obj_get_int(channel_obj);
    uint8_t id=(uint8_t)mp_obj_get_int(id_obj);
    uint8_t len=(uint8_t)mp_obj_get_int(len_obj);
    if(len==0 || len>9) mp_raise_ValueError(MP_ERROR_TEXT("raw LIN length must be 1..9"));
    uint8_t buf[9];
    int r=lin_master_request_raw(channel,id,buf,len,100);
    if(r!=LIN_OK) mp_raise_OSError(-r);
    return mp_obj_new_bytes(buf,len);
}
static MP_DEFINE_CONST_FUN_OBJ_3(mod_lin_request_raw_obj,mod_lin_request_raw);

static mp_obj_t mod_lin_slave_set(size_t n,const mp_obj_t *a) {
    uint8_t channel=(uint8_t)mp_obj_get_int(a[0]);
    uint8_t id=(uint8_t)mp_obj_get_int(a[1]);
    mp_buffer_info_t b;
    mp_get_buffer_raise(a[2],&b,MP_BUFFER_READ);
    if(b.len>8) mp_raise_ValueError(MP_ERROR_TEXT("LIN data > 8 bytes"));
    lin_checksum_mode_t m=(n>3&&!mp_obj_is_true(a[3]))?LIN_CHECKSUM_CLASSIC:LIN_CHECKSUM_ENHANCED;
    int r=lin_slave_set(channel,id,b.buf,b.len,m);
    if(r!=LIN_OK) mp_raise_OSError(-r);
    return mp_const_none;
}
static MP_DEFINE_CONST_FUN_OBJ_VAR_BETWEEN(mod_lin_slave_set_obj,3,4,mod_lin_slave_set);

static mp_obj_t mod_lin_slave_clear(mp_obj_t channel_obj) {
    uint8_t channel=(uint8_t)mp_obj_get_int(channel_obj);
    int r=lin_slave_clear(channel);
    if(r!=LIN_OK) mp_raise_OSError(-r);
    return mp_const_none;
}
static MP_DEFINE_CONST_FUN_OBJ_1(mod_lin_slave_clear_obj,mod_lin_slave_clear);

static const mp_rom_map_elem_t globals_table[]={
    {MP_ROM_QSTR(MP_QSTR___name__),MP_ROM_QSTR(MP_QSTR_lin)},
    {MP_ROM_QSTR(MP_QSTR_init),MP_ROM_PTR(&mod_lin_init_obj)},
    {MP_ROM_QSTR(MP_QSTR_send),MP_ROM_PTR(&mod_lin_send_obj)},
    {MP_ROM_QSTR(MP_QSTR_request),MP_ROM_PTR(&mod_lin_request_obj)},
    {MP_ROM_QSTR(MP_QSTR_request_raw),MP_ROM_PTR(&mod_lin_request_raw_obj)},
    {MP_ROM_QSTR(MP_QSTR_slave_set),MP_ROM_PTR(&mod_lin_slave_set_obj)},
    {MP_ROM_QSTR(MP_QSTR_slave_clear),MP_ROM_PTR(&mod_lin_slave_clear_obj)},
};
static MP_DEFINE_CONST_DICT(globals,globals_table);
const mp_obj_module_t lin_module={.base={&mp_type_module},.globals=(mp_obj_dict_t*)&globals};
MP_REGISTER_MODULE(MP_QSTR_lin,lin_module);
#endif
