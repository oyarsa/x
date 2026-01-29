#!/bin/bash
set -euo pipefail

USER=dev

if id "$USER" &>/dev/null; then
    echo "User '$USER' already exists, skipping creation"
else
    echo "Creating user '$USER'..."
    useradd -m -s /bin/bash "$USER"
    echo "$USER ALL=(ALL) NOPASSWD:ALL" > /etc/sudoers.d/$USER
    chmod 440 /etc/sudoers.d/$USER
    mkdir -p /home/$USER/.ssh
    cp ~/.ssh/authorized_keys /home/$USER/.ssh/
    chown -R $USER:$USER /home/$USER/.ssh
    chmod 700 /home/$USER/.ssh
    chmod 600 /home/$USER/.ssh/authorized_keys
    echo "User '$USER' created with sudo access"
fi
