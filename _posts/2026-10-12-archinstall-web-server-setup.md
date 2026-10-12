---
tags: ["archlinux", "security", "luks", "yubikey", "self-hosting"]
categories: ["linux", "tooling"]
title: "Archinstall Web Server Setup: Hardening a 10-Year NUC"
image:
  path: /assets/img/2026-10-12/main.jpg
  alt: A retro mechanical lock switch anchored to a compact metal chassis with clean network lines.
---

Can an old 17-watt box from 2013 with a 1.1 GHz Celeron still run a hardened, encrypted web server in 2026? Yes - if you do not fight the hardware.

I had an Intel NUC Kit DCCP847DYE gathering dust under my desk. It has two slow cores, 8 GB of DDR3 memory, and an mSATA SSD. I wanted to turn it into an encrypted, self-hosted web server without exposing my home network to the entire internet.

Installing Arch Linux used to mean typing thirty manual disk partitioning and cryptsetup commands from memory. With the redesigned **Archinstall 4.x**, the installer has a completely overhauled Textual interface with built-in toggles for Unified Kernel Images, Btrfs snapshots, and firewalls.

Here is how to set up the installer for Polish localization, full disk encryption, and production-grade security on modest hardware.

## Step 1: Navigating Archinstall 4.x

Boot into the latest Arch Linux live ISO and run the guided installer:

```bash
archinstall
```

```text
                  Archinstall (Textual TUI)
 1. Archinstall language       [en]
 2. Locales                    [pl, pl_PL.UTF-8]
 3. Mirrors and repositories   [Poland, multilib: off]
 4. Disk configuration         [Btrfs, LUKS2, Snapper]
 5. Swap                       [zram: enabled]
 6. Bootloader                 [systemd-boot, UKI: on]
 7. Kernels                    [linux-hardened]
 8. Additional firmware        [intel-ucode]
 9. Hostname                   [nucbox]
10. Authentication             [root disabled, user: sudo]
11. Profile                    [Minimal]
12. Applications               [Firewall: UFW]
13. Network configuration      [NetworkManager]
14. Pacman                     [Parallel: 5]
15. Additional packages        [caddy, cloudflared, apparmor]
16. Timezone                   [Europe/Warsaw]
17. Automatic time sync (NTP)  [True]
```

Earlier guides talk about the old menu, but version 4.x organizes settings into cleaner groups.

### Locales and console fonts

Enter the **Locales** submenu:
- **Keyboard layout:** Pick `pl`.
- **Locale language:** Pick `pl_PL.UTF-8` for full Polish system messages, or `en_US.UTF-8` if you prefer terminal logs in English.
- **Console font:** Select `Lat2-Terminus16` or `eurlatgr`.

Without a Latin-2 font, Polish letters like `ą`, `ć`, and `ł` display as unreadable hollow blocks in the virtual console before your display manager loads.

### Partitioning, LUKS, and Snapper

Enter the **Disk configuration** submenu:
- Select your mSATA drive (`/dev/sda`).
- Choose **Use a best-effort default partition layout** with **`btrfs`**.
- In **Btrfs snapshots**, select **`Snapper`**. Archinstall configures automatic subvolume rollbacks for you.
- In **Disk encryption**, choose **`LUKS`**, enter your passphrase, and leave the default iteration time at 2000 ms.

### Bootloader and hardened kernel

- Under **Bootloader**, select **`systemd-boot`** and set **Unified kernel images (UKI)** to **`Enabled`**. UKIs combine the kernel, initramfs, and boot parameters into one cohesive EFI binary.
- Under **Kernels**, select **`linux-hardened`** for memory exploit mitigations and user-namespace restrictions.
- In **Applications**, toggle **Firewall** to **`UFW`**.

Hit **Install** and let the script download and configure your base system.

## Step 2: The hardware reality of an older Celeron

Once the system reboots into your fresh installation, you must address two hardware limitations of the Celeron 847 processor:

1. **No AES-NI:** This CPU has no hardware AES acceleration.
2. **No TPM 2.0 or modern Secure Boot:** The 2013 BIOS does not support automated TPM key sealing.

### Testing the cipher overhead

Check the difference software AES makes on your CPU:

```bash
cryptsetup benchmark
```

```text
# Tests are approximate using memory only.
#  Algorithm |       Key |      Encryption |      Decryption
     aes-xts        256b        84.2 MiB/s        86.1 MiB/s
chacha20-poly1305   256b       212.4 MiB/s       214.0 MiB/s
```

Without AES-NI, software AES caps disk throughput at roughly 85 MiB/s while running both cores hot. For secondary drives or backups on older CPUs, the modern **Adiantum** cipher (`xchacha12,aes-adiantum-plain64`) gives near native speeds at low CPU overhead.

### Firmware protection

Because there is no TPM chip to bind the boot sequence, guard physical access through your firmware:

1. Press `F2` at startup to open the Intel Visual BIOS.
2. Set a strong **Supervisor/Admin password**.
3. Disable boot from external USB devices and network PXE.

## Step 3: Unlocking LUKS with a YubiKey (FIDO2)

Typing a 30-character encryption passphrase on every reboot gets old fast. Because the NUC lacks a TPM 2.0 chip, the cleanest modern alternative is binding LUKS2 to a **YubiKey via FIDO2**.

First, install the user-space library:

```bash
sudo pacman -S libfido2
```

```text
resolving dependencies...
looking for conflicting packages...
Packages (1) libfido2-1.15.0-1
Total Installed Size:  0.41 MiB
```

Plug in your YubiKey and bind it to the encrypted partition:

```bash
sudo systemd-cryptenroll --fido2-device=auto /dev/sda2
```

```text
Enrolled FIDO2 token on keyslot 1.
```

Your original password stays safe in keyslot 0 as a recovery fallback.

### Configuring early boot hooks

To let systemd unlock the device before mounting root, switch your initramfs hooks to `systemd` and `sd-encrypt` in `/etc/mkinitcpio.conf`:

```ini
HOOKS=(base systemd autodetect keyboard sd-vconsole modconf block sd-encrypt filesystems fsck)
```

Point the initramfs to your FIDO2 device in `/etc/crypttab.initramfs`:

```text
root UUID=4a91b6e4-802c-47ea-a06f-12903487abcd - fido2-device=auto
```

Regenerate your boot images:

```bash
sudo mkinitcpio -P
```

```text
==> Building image from preset: /etc/mkinitcpio.d/linux-hardened.preset
  -> Successfully generated image: '/boot/initramfs-linux-hardened.img'
```

When you power on the machine, the YubiKey LED flashes. Touch the gold button, and the drive decrypts instantly. If the key is not plugged in, boot waits briefly and drops back to the standard password prompt.

## Step 4: Enabling AppArmor and the firewall

Turn on Mandatory Access Control to isolate system daemons:

```bash
sudo systemctl enable --now apparmor.service
```

```text
Created symlink /etc/systemd/system/multi-user.target.wants/apparmor.service -> /usr/lib/systemd/system/apparmor.service.
```

Activate the UFW firewall installed by Archinstall:

```bash
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw enable
```

```text
Firewall is active and enabled on system startup
```

## Step 5: Hosting safely with Cloudflare Tunnel

Opening ports 80 and 443 on your home router exposes your residential IP address to automated botnets and port scanners.

Instead, route traffic through an outbound encrypted tunnel:

```bash
cloudflared tunnel login
```

```text
A browser window should have opened. If not, open this URL:
https://dash.cloudflare.com/argotunnel?callback=...
Successfully fetched origin cert.
```

Create a tunnel named `nuc-web`:

```bash
cloudflared tunnel create nuc-web
```

```text
Created tunnel nuc-web with id 4a91b6e4-802c-47ea-a06f-12903487abcd
```

Map your domain to the local web server in `~/.cloudflared/config.yml`:

```yaml
tunnel: 4a91b6e4-802c-47ea-a06f-12903487abcd
credentials-file: /etc/cloudflared/4a91b6e4-802c-47ea-a06f-12903487abcd.json

ingress:
  - hostname: yourdomain.com
    service: http://localhost:80
  - service: http_status:404
```

Route the DNS record and start the tunnel as a background service:

```bash
cloudflared tunnel route dns nuc-web yourdomain.com
sudo systemctl enable --now cloudflared
```

```text
Created symlink /etc/systemd/system/multi-user.target.wants/cloudflared.service -> /usr/lib/systemd/system/cloudflared.service.
```

Your website is live over HTTPS with **zero open router ports**.

## Step 6: Sandboxing the Caddy web server

Caddy serves static files with negligible memory overhead. Configure `/etc/caddy/Caddyfile`:

```caddy
:80 {
    root * /var/www/yoursite
    file_server
    encode zstd gzip
}
```

Lock down the process using systemd isolation flags by editing the service overrides:

```bash
sudo systemctl edit caddy
```

Add these security boundaries:

```ini
[Service]
ProtectSystem=strict
ProtectHome=yes
PrivateDevices=yes
PrivateTmp=yes
NoNewPrivileges=yes
ReadOnlyPaths=/var/www/yoursite
```

Start Caddy:

```bash
sudo systemctl enable --now caddy
```

```text
Created symlink /etc/systemd/system/multi-user.target.wants/caddy.service -> /usr/lib/systemd/system/caddy.service.
```

Even if an attacker finds an exploit in your web server, systemd blocks access to user directories, block devices, and root binaries.

## Step 7: Keeping a rolling-release server up to date

Running a rolling-release distribution on an unattended home server requires a balance between staying patched and avoiding surprise breakages.

Because we chose Btrfs and Snapper in Archinstall, we can add a foolproof safety net.

### Automatic snapshots before every update

Install `snap-pac` to take pre- and post-transaction snapshots whenever `pacman` modifies the system:

```bash
sudo pacman -S snap-pac
```

```text
Packages (1) snap-pac-3.0.1-2
Total Installed Size: 0.03 MiB
```

If a new kernel or glibc update ever breaks boot or networking, you can roll back to the exact snapshot taken seconds before the upgrade.

### Checking updates safely

Avoid unattended automated upgrades on Arch. Instead, use `checkupdates` to safely check for pending patches without touching your live package databases:

```bash
sudo pacman -S pacman-contrib
checkupdates
```

```text
linux-hardened 6.11.2.hardened1-1 -> 6.11.3.hardened1-1
caddy 2.8.4-1 -> 2.8.5-1
cloudflared 2024.9.1-1 -> 2024.10.0-1
```

When you are ready to apply updates, run standard upgrades manually:

```bash
sudo pacman -Syu
```

### Cleaning the package cache

Pacman keeps every downloaded `.pkg.tar.zst` file in `/var/cache/pacman/pkg/`. On a small mSATA SSD, this cache will eventually fill your drive.

Enable the systemd timer to trim old package versions automatically every week:

```bash
sudo systemctl enable --now paccache.timer
```

```text
Created symlink /etc/systemd/system/timers.target.wants/paccache.timer -> /usr/lib/systemd/system/paccache.timer.
```

### Knowing when to reboot

After applying updates, check whether the running kernel or critical daemons need a restart:

```bash
sudo pacman -S needrestart
sudo needrestart
```

```text
Scanning processes...
Scanning candidates...
NEEDRESTART: Kernel update detected. Reboot required.
```

Reboot when required, tap your YubiKey to unlock the drive, and your sandboxed web services will resume immediately.

## Summary

- **Archinstall 4.x** makes hardened setups practical: UKIs, Snapper subvolumes, and UFW firewalls are now simple menu toggles.
- **Console fonts matter**: Pick `Lat2-Terminus16` during setup so Polish diacritics render cleanly in the TTY.
- **YubiKey replaces typing passphrases**: Enrolling FIDO2 via systemd-cryptenroll and the sd-encrypt hook gives instant hardware-touch unlocking with password fallback.
- **Respect old hardware**: A 1.1 GHz Celeron without AES-NI struggles with heavy encryption algorithms, but runs lightweight tools like Caddy and Cloudflare Tunnel smoothly.
- **Never open inbound router ports**: Use an outbound tunnel to protect your home network while keeping the site fast and responsive.
- **Update with a safety net**: Pair snap-pac with Snapper for automatic pre-upgrade snapshots, and use paccache.timer to prevent your mSATA SSD from running out of space.

Keep your old hardware out of the landfill - a silent 15-watt box makes an ideal private server when configured with care.

## Resources

- [Archinstall GitHub Repository](https://github.com/archlinux/archinstall/tree/78982a624824aa415f59bf88c515676a589e3c55) - Source code and documentation for the Archinstall Textual TUI release.
- [ArchWiki: dm-crypt and Full Disk Encryption](https://wiki.archlinux.org/title/Dm-crypt/Encrypting_an_entire_system) - Comprehensive guide to configuring LUKS block devices on Arch Linux.
- [ArchWiki: systemd-cryptenroll](https://wiki.archlinux.org/title/Systemd-cryptenroll) - Official Arch Linux guide for enrolling FIDO2 tokens into LUKS2 volumes.
- [ArchWiki: System Maintenance](https://wiki.archlinux.org/title/System_maintenance) - Official guide on pacman cache maintenance, news review, and package upgrades.
- [Caddy Server Repository](https://github.com/caddyserver/caddy/tree/7088605cc11c52c2777ab613dfc5c2a9816006e4) - Official repository for the Caddy web server.
- [Cloudflare Tunnel Documentation](https://github.com/cloudflare/cloudflared/tree/628176a2d64c723f637a1877a109d1c9c779df21) - Source code and configuration guides for `cloudflared`.
