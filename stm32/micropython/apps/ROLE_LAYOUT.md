# Standard runtime instance layout

The standard BE-IIS LIN runtime uses these instance names:

```text
master_tx_query
master_rx_query
master_native

slave_tx_query
slave_rx_query
slave_native

logging_tx_query
logging_rx_query
logging_native
```

Message routing is handled by the central runtime dispatcher and per-instance
mailboxes.

For each functional group:

```text
host/application
      |
      v
*_tx_query
      |
      v
*_native
      |
      v
*_rx_query
      |
      v
host/application
```

Only the `*_native` instance owns the corresponding hardware/native function.
The query instances are communication endpoints and must not directly own LIN
hardware resources.

The logging group follows the same structure. Physical passive LIN sniffing is
a separate native feature and must not be faked in Python when the native RX
queue is unavailable.
