#!/bin/bash
if nc -zw10 192.168.0.11 5000; then
    python3 -m ftp_sync -c $1 sync-all
fi
