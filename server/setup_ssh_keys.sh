for i in $(seq -w 1 20); do
    ssh-copy-id -o StrictHostKeyChecking=no pi@rpi-D$i.local
    ssh-copy-id pi@rpi-A$i.local
done
for i in $(seq -w 1 20); do
    ssh-copy-id -o StrictHostKeyChecking=no pi@rpi-D$i.local
    ssh-copy-id pi@rpi-B$i.local
done
for i in $(seq -w 1 20); do
    ssh-copy-id -o StrictHostKeyChecking=no pi@rpi-D$i.local
    ssh-copy-id pi@rpi-C$i.local
done
for i in $(seq -w 1 20); do
    ssh-copy-id -o StrictHostKeyChecking=no pi@rpi-D$i.local
    ssh-copy-id pi@rpi-D$i.local
done
for i in $(seq -w 1 20); do
    ssh-copy-id -o StrictHostKeyChecking=no pi@rpi-D$i.local
    ssh-copy-id pi@rpi-E$i.local
done
for i in $(seq -w 1 20); do
    ssh-copy-id -o StrictHostKeyChecking=no pi@rpi-D$i.local
    ssh-copy-id pi@rpi-F$i.local
done
for i in $(seq -w 1 20); do
    ssh-copy-id -o StrictHostKeyChecking=no pi@rpi-D$i.local
    ssh-copy-id pi@rpi-G$i.local
done
