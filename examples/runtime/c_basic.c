#define _GNU_SOURCE
#include <errno.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/socket.h>
#include <sys/un.h>
#include <unistd.h>

#define DEFAULT_SOCKET "/run/beiis/lin-hat.sock"
#define BUF_SIZE 65536

static int connect_daemon(const char *path) {
    int fd = socket(AF_UNIX, SOCK_SEQPACKET, 0);
    if (fd < 0) {
        perror("socket");
        exit(1);
    }

    struct sockaddr_un addr;
    memset(&addr, 0, sizeof(addr));
    addr.sun_family = AF_UNIX;

    if (strlen(path) >= sizeof(addr.sun_path)) {
        fprintf(stderr, "socket path too long\n");
        exit(1);
    }
    strcpy(addr.sun_path, path);

    if (connect(fd, (struct sockaddr *)&addr, sizeof(addr)) < 0) {
        perror("connect");
        exit(1);
    }
    return fd;
}

static const char *rpc(int fd, const char *json, char *reply, size_t reply_size) {
    size_t len = strlen(json);
    if (send(fd, json, len, 0) != (ssize_t)len) {
        perror("send");
        exit(1);
    }

    ssize_t n = recv(fd, reply, reply_size - 1, 0);
    if (n < 0) {
        perror("recv");
        exit(1);
    }
    reply[n] = '\0';

    if (strstr(reply, "\"ok\":false") != NULL) {
        fprintf(stderr, "daemon error: %s\n", reply);
        exit(1);
    }
    return reply;
}

/*
 * Minimal demonstration parser only.
 * Production code should use a real JSON parser.
 */
static int result_data_hex(const char *json, char *out, size_t out_size) {
    const char *p = strstr(json, "\"data\":\"");
    if (!p)
        return -1;
    p += strlen("\"data\":\"");

    const char *end = strchr(p, '"');
    if (!end)
        return -1;

    size_t len = (size_t)(end - p);
    if (len + 1 > out_size)
        return -1;

    memcpy(out, p, len);
    out[len] = '\0';
    return 0;
}

int main(int argc, char **argv) {
    const char *path = argc > 1 ? argv[1] : DEFAULT_SOCKET;
    char reply[BUF_SIZE];
    char data_hex[4096];

    int fd = connect_daemon(path);

    /*
     * Standard master runtime path:
     *   slot 0 master_tx_query
     *   slot 1 master_rx_query
     */

    rpc(
        fd,
        "{\"v\":1,\"id\":1,\"type\":\"request\","
        "\"op\":\"set_active_instance\","
        "\"args\":{\"instance\":0}}",
        reply,
        sizeof(reply)
    );
    printf("select master: %s\n", reply);

    /* Native PING request is one byte: 0x00. */
    rpc(
        fd,
        "{\"v\":1,\"id\":2,\"type\":\"request\","
        "\"op\":\"data_send\","
        "\"args\":{\"channel\":0,\"data\":\"00\"}}",
        reply,
        sizeof(reply)
    );
    printf("send: %s\n", reply);

    rpc(
        fd,
        "{\"v\":1,\"id\":3,\"type\":\"request\","
        "\"op\":\"data_recv\","
        "\"args\":{\"instance\":1,\"channel\":0,\"timeout\":2.0}}",
        reply,
        sizeof(reply)
    );
    printf("receive: %s\n", reply);

    if (result_data_hex(reply, data_hex, sizeof(data_hex)) < 0) {
        fprintf(stderr, "could not extract result data\n");
        close(fd);
        return 1;
    }

    if (strcmp(data_hex, "0000") != 0) {
        fprintf(stderr, "unexpected native PING reply: %s\n", data_hex);
        close(fd);
        return 1;
    }

    puts("master native PING: OK");
    close(fd);
    return 0;
}
