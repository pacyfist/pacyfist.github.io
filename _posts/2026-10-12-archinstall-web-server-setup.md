---
tags: ["archlinux", "security", "luks", "yubikey", "self-hosting"]
categories: ["linux", "tooling"]
title: "Archinstall Web Server Setup: Hardening a 10-Year NUC"
image:
  path: /assets/img/2026-10-12/main.jpg
  alt: A 2013 Intel NUC dressed up like Fort Knox and refusing to retire.
---

Can a 17-watt Intel NUC DCCP847DYE from 2013 - a tiny box gathering dust under my desk with a 1.1 GHz Celeron and 8 GB of DDR3 - still run an encrypted, hardened web server in 2026? Do you think it would choke? I thought so too, until I stopped fighting the hardware.

I wanted to turn this dual-core relic and its mSATA SSD into a self-hosted web server without opening a single port on my home router.

Installing Arch Linux used to feel like defusing a bomb by typing thirty disk-partitioning and encryption commands from memory. With **Archinstall 4.5**, the guided installer gives you a clean Textual TUI menu with built-in support for Btrfs snapshots, compressed RAM swap, YubiKey hardware keys, and firewalls.

Here is the complete walk-through of every menu option in Archinstall 4.5 for Polish localization, full disk encryption, and lock-tight security on this specific NUC.

## Step 1: Every Menu Option in Archinstall 4.5

Boot into the latest Arch Linux live ISO. If you have a Polish keyboard plugged directly into the NUC, load the keymap first so the encryption passphrase you type now matches the layout after reboot:

```bash
loadkeys pl
archinstall
```

```text
                        Archinstall 4.5 (Textual TUI)
 [ ] Archinstall language       [English]
 [✓] Locales                    [kb: pl, lang: en_US.UTF-8, font: Lat2-Terminus16]
 [✓] Mirrors and repositories   [Poland]
 [✓] Disk configuration         [Btrfs, Subvolumes, zstd, LUKS, Snapper]
 [✓] Swap                       [zram: Enabled, algo: lz4]
 [✓] Bootloader                 [Grub]
 [✓] Kernels                    [linux-hardened]
 [ ] Additional firmware        []
 [✓] Hostname                   [nucbox]
 [✓] Authentication             [user: sudo]
 [✓] Profile                    [Server: sshd]
 [✓] Applications               [Firewall: ufw]
 [✓] Network configuration      [Copy ISO network configuration to installation]
 [ ] Pacman                     [Parallel Downloads: 5, Color: True]
 [✓] Additional packages        [caddy, cloudflared, apparmor]
 [✓] Timezone                   [Europe/Warsaw]
 [ ] Automatic time sync (NTP)  [Enabled]
```

Here is the exact breakdown of all 17 menu items from top to bottom, grouped into five quick stages so you do not miss the hidden headless-server traps.

### Items 1-3: Language, Polish Locales, and Mirrors

- **1. Archinstall language:** Leave at **`English`**. This only changes the installer's own menus, not the system you are installing.
- **2. Locales:** Open the submenu and configure its four items:
  - **Keyboard layout:** Pick **`pl`**.
  - **Locale language:** Pick **`en_US.UTF-8`** to keep system error logs in English (much easier to search online when debugging), or **`pl_PL.UTF-8`** for Polish messages.
  - **Locale encoding:** Leave at **`UTF-8`**.
  - **Console font:** Change `default8x16` to **`Lat2-Terminus16`** (or `eurlatgr`). The default font does not know how to draw central European letters, turning Polish characters like `ą`, `ć`, and `ł` into unreadable hollow blocks on a physical monitor.
- **3. Mirrors and repositories:**
  - **Select regions:** Pick **`Poland`** (or your country). Archinstall tests and ranks the fastest local mirrors in `/etc/pacman.d/mirrorlist`.
  - **Optional repositories:** Leave `multilib` and all `testing` repositories **unchecked**. A 64-bit web server has no use for 32-bit gaming libraries or unstable test packages.

### Items 4-5: Disk Configuration and ZRAM Swap

- **4. Disk configuration:** Open the menu and walk through its four submenus in order:
  1. **Partitioning:**
     - **Layout:** Pick **`Use a best-effort default partition layout`** on your mSATA SSD (`/dev/sda`). Archinstall creates an unencrypted 1 GiB FAT32 `/boot` partition (`/dev/sda1`) and places your encrypted root container on `/dev/sda2`.
     - **Filesystem:** Pick **`btrfs`** and choose **`Yes`** for default subvolumes. Think of subvolumes like movable room dividers inside one apartment: `@` holds your OS (`/`), `@home` holds user files, `@log` holds `/var/log`, and `@pkg` holds the package cache. Rolling back a broken OS update on `@` never wipes your logs or `/home`.
     - **Compression:** Pick **`Use compression`** (`compress=zstd`). Our 2013 Celeron lacks hardware AES-NI encryption circuitry, so it has to encrypt every byte in software at around 85 MiB/s. Compressing text configs and logs first is like vacuum-sealing winter clothes before loading a small car - the CPU has fewer bytes to encrypt, and the mSATA SSD takes less write wear.
  2. **LVM:** Leave unconfigured. Btrfs subvolumes already handle volume management without extra layering.
  3. **Disk encryption:**
     - **Encryption type:** Select **`LUKS`** and set a strong backup passphrase.
     - **Iteration time:** Archinstall 4.5 raised the default to `10000` ms (10 seconds). Iteration time is a deliberate speed bump that forces password-guessing tools to wait before each try. On a slow 1.1 GHz Celeron, a 10-second target tuned for modern CPUs makes manual typing feel sluggish. Lower it to **`3000`** ms for keyboard unlocks, or leave it at **`10000`** ms if you unlock via YubiKey.
     - **Partitions:** Mark **`/dev/sda2`**. **Watch out for this trap:** if you forget to highlight `/dev/sda2` here, Archinstall 4.5 quietly ignores your password and installs without encryption!
     - **HSM:** If your YubiKey is already plugged in, select it here (`Select a FIDO2 device to use for HSM`). Archinstall 4.5 will enroll the key via `systemd-cryptenroll`, install `libfido2`, configure `systemd` and `sd-encrypt` in `/etc/mkinitcpio.conf`, and add `rd.luks.options=fido2-device=auto` automatically. (If you prefer to set up the YubiKey after first boot, leave **HSM** unset and follow Step 3.)
  4. **Btrfs snapshots:** Select **`Snapper`**.
- **5. Swap (ZRAM):** Choose **`Yes`** for **Swap on zram**, then change the compression algorithm from the default `zstd` to **`lz4`** (out of `zstd`, `lzo-rle`, `lzo`, `lz4`, and `lz4hc`).
  - **Why `lz4` wins on the NUC:** ZRAM acts like a compressed zip folder inside your 8 GB of RAM so the system rarely touches the slow SSD when memory gets tight. While `zstd` squeezes data slightly smaller, our dual-core Celeron 847 is strictly CPU-bound. `lz4` compresses memory pages at a fraction of the CPU cost, preventing stalls under load.

### Items 6-8: Bootloader, Hardened Kernel, and Firmware

- **6. Bootloader:** When you open **Bootloader** on the DCCP847DYE, you will likely see:

```text
UEFI is not detected and some options are disabled
```

  By default, the 2013 Intel Visual BIOS boots USB sticks in Legacy BIOS (CSM) mode unless UEFI is manually toggled in the `F2` setup menu. When `/sys/firmware/efi` is absent, Archinstall 4.5 hides UEFI-only bootloaders (`Systemd-boot`, `Efistub`, `Refind`) and shows **`Grub`** and **`Limine`**.
  - **Best choice:** Pick **`Grub`** (and leave **Plymouth** disabled so boot splashes never hide the LUKS prompt). You do not need to exit the installer to change BIOS modes - GRUB boots cleanly from the unencrypted `/dev/sda1` partition in both BIOS and UEFI modes. Better yet, when Archinstall 4.5 sees **`Grub` + `Btrfs` + `Snapper`**, it automatically installs `grub-btrfs` and `inotify-tools` and enables `grub-btrfsd.service`. Every Snapper snapshot shows up right on your GRUB menu like a video game save point you can boot into if an update goes sideways.
- **7. Kernels:** Uncheck `linux` and select **`linux-hardened`**. It trades a tiny slice of desktop gaming speed for stricter memory allocator checks and `/proc` protections. Optionally also select **`linux-lts`** as a backup kernel.
- **8. Additional firmware:** **Leave completely empty (`[]`).** When you open this menu, you only see six obscure data-center packages (`linux-firmware-liquidio`, `mellanox`, `qlogic`, etc.) and no `intel-ucode`. Do not worry - Archinstall 4.5 checks `/proc/cpuinfo` automatically, detects `GenuineIntel`, and installs both `intel-ucode` and standard `linux-firmware` in the background.

### Items 9-11: Hostname, Authentication, and Server Profile

- **9. Hostname:** Enter **`nucbox`** (or your preferred name).
- **10. Authentication (and the U2F closet trap):**
  - **Root password:** Leave blank (press Enter to skip) so direct `root` login stays locked.
  - **User account:** Select **`Add a user`**, set your username and password, and choose **`Yes`** for superuser (`sudo`) access.
  - **U2F login setup:** **Leave unconfigured!**
  - **Why this is a trap on a headless server:** Your YubiKey will stay plugged into the NUC in a closet so it can unlock the encrypted drive after power outages. If you configure `U2F login setup` here, Archinstall installs `pam-u2f` and puts `pam_u2f.so` at the top of `/etc/pam.d/system-login` and `/etc/pam.d/sudo`. Every time you SSH in from the couch and run `sudo`, Linux will see the plugged-in YubiKey and freeze waiting for you to walk to the closet and press the flashing gold button (`Please touch the device.`).
- **11. Profile:** Pick **`Server`** -> **`sshd`** (from the list of `Cockpit`, `Docker`, `httpd`, `Lighttpd`, `Mariadb`, `Nginx`, `Postgresql`, `sshd`, and `Tomcat`). This installs `openssh` and enables `sshd.service` out of the box.

### Items 12-17: Firewall, Networking, Packages, and Time

- **12. Applications (and the UFW lockout trap):** Leave Bluetooth, Audio, Print service, and Additional fonts unconfigured (Power management is automatically greyed out because a NUC has no laptop battery), and set **Firewall** to **`ufw`**.
  - **Watch out for the SSH lockout:** In Archinstall 4.5, selecting `ufw` enables `ufw.service` **and** rewrites `/etc/ufw/ufw.conf` to `ENABLED=yes` with a default policy of `DROP`. If you reboot right after installing, port 22 is blocked! We will add the LAN SSH rule in the post-install chroot below.
- **13. Network configuration:** Pick **`Copy ISO network configuration to installation`**. Because your NUC is already online over Ethernet in the live ISO, this copies `/etc/systemd/network/20-ethernet.network` and enables built-in `systemd-networkd` and `systemd-resolved` with **zero extra packages** and lower RAM usage than `NetworkManager`.
- **14. Pacman:** Leave defaults (`Parallel Downloads: 5`, `Color: True`).
- **15. Additional packages:** Search and add **`caddy`** (web server), **`cloudflared`** (Cloudflare Tunnel client), and **`apparmor`** (process confinement).
- **16. Timezone & 17. Automatic time sync (NTP):** Select **`Europe/Warsaw`** and leave **NTP** **`Enabled`** so TLS certificates and FIDO2 checks never fail from clock drift.

### Installing and allowing LAN SSH before first boot

Select **Install** at the bottom of the main menu and confirm **`Yes`**. When installation finishes, Archinstall 4.5 asks:

```text
Installation completed in 2m14s
What would you like to do next?
  Exit archinstall
  Reboot system
> chroot into installation for post-installation configurations
```

Pick **`chroot into installation for post-installation configurations`** so you can allow SSH from your home network before UFW blocks port 22 on first boot (check your LAN subnet with `ip -4 addr` and adjust `192.168.1.0/24` if your router uses `192.168.0.0/24` or similar):

```bash
ufw allow from 192.168.1.0/24 to any port 22 proto tcp
exit
```

```text
Rules updated
```

Now select **Reboot system** and pull out the installer USB stick as the screen goes black.

## Step 2: First Boot, BIOS Lockdown, and Cipher Speed

Our 2013 Celeron 847 has two hardware limits we need to respect: it has **no TPM 2.0 chip** to seal boot keys automatically, and **no AES-NI instructions** to accelerate encryption in hardware.

### Locking down the Intel Visual BIOS

Because there is no TPM chip, anyone with physical access could plug in a live USB stick if you leave the firmware wide open. As the NUC reboots for the first time:

1. Press `F2` at startup to enter the Intel Visual BIOS.
2. Set a strong **Supervisor/Admin password**.
3. Disable booting from external USB drives and network PXE so the NUC only boots from its internal mSATA SSD.

Save with `F10` and let the NUC boot into your fresh Arch installation.

### Measuring the software encryption ceiling

Once logged in, run a quick memory benchmark to see why we enabled Btrfs `zstd` compression in Step 1:

```bash
cryptsetup benchmark
```

```text
# Tests are approximate using memory only.
#  Algorithm |       Key |      Encryption |      Decryption
     aes-xts        256b        84.2 MiB/s        86.1 MiB/s
chacha20-poly1305   256b       212.4 MiB/s       214.0 MiB/s
```

Without hardware AES-NI, software `aes-xts` maxes out around 85 MiB/s while running both CPU cores hot. Compressing text files and logs with `zstd` before they hit LUKS shrinks the amount of data the CPU has to encrypt. (If you ever attach a secondary USB backup drive to an older CPU like this, formatting it with the modern **Adiantum** cipher - `xchacha12,aes-adiantum-plain64` - delivers near-native SSD speeds with minimal CPU load.)

## Step 3: Unlocking LUKS with a YubiKey (FIDO2)

Typing a 30-character passphrase on a physical keyboard after every reboot gets old fast. Because the NUC lacks a TPM 2.0 chip, binding LUKS2 to a **YubiKey via FIDO2** gives us one-tap unlocking.

If you already selected your YubiKey under **Disk configuration -> Disk encryption -> HSM** during Step 1, Archinstall 4.5 has already configured everything below. **Skip straight to Step 4.**

If you left **HSM** blank during installation, set it up now. First, install `libfido2`:

```bash
sudo pacman -S libfido2
```

```text
resolving dependencies...
looking for conflicting packages...
Packages (1) libfido2-1.17.0-1
Total Installed Size:  0.47 MiB
```

Plug in your YubiKey and enroll it into your encrypted root partition:

```bash
sudo systemd-cryptenroll --fido2-device=auto /dev/sda2
```

```text
Enrolled FIDO2 token on keyslot 1.
```

Your original passphrase stays untouched in keyslot 0 as a backup recovery key.

### Teaching early boot to talk to your YubiKey

When you skip **HSM** during installation, the tiny startup environment that unlocks your drive (the **initramfs**) uses older scripts (`udev` and `encrypt`) that do not speak FIDO2.

Open `/etc/mkinitcpio.conf` and replace `udev`, `keymap`, `consolefont`, and `encrypt` with their modern systemd equivalents (`systemd`, `sd-vconsole`, and `sd-encrypt`) so early boot can talk to USB security keys:

```ini
HOOKS=(base systemd autodetect microcode modconf kms keyboard sd-vconsole block sd-encrypt filesystems fsck)
```

Next, check the LUKS UUID of `/dev/sda2`:

```bash
sudo blkid -s UUID -o value /dev/sda2
```

```text
4a91b6e4-802c-47ea-a06f-12903487abcd
```

Open `/etc/default/grub` and update `GRUB_CMDLINE_LINUX` to use `rd.luks.name` and `fido2-device=auto`, keeping your existing mapper name (`root`) and Btrfs `rootflags=subvol=@ rw` intact:

```ini
GRUB_CMDLINE_LINUX="rd.luks.name=4a91b6e4-802c-47ea-a06f-12903487abcd=root rd.luks.options=fido2-device=auto,password-echo=no root=/dev/mapper/root rootflags=subvol=@ rw"
```

Rebuild the initramfs and GRUB menu:

```bash
sudo mkinitcpio -P
sudo grub-mkconfig -o /boot/grub/grub.cfg
```

```text
==> Building image from preset: /etc/mkinitcpio.d/linux-hardened.preset
  -> Successfully generated image: '/boot/initramfs-linux-hardened.img'
Generating grub configuration file ...
Found linux image: /boot/vmlinuz-linux-hardened
Found Intel Microcode image
Found initrd image: /boot/initramfs-linux-hardened.img
done
```

On the next boot, the YubiKey LED flashes. Touch the gold button and the drive unlocks immediately. If the key is unplugged, boot waits a few seconds and falls back to the keyboard passphrase prompt.

## Step 4: Turning on AppArmor and Checking the Firewall

Standard Linux permissions only check *who* is running a program. **AppArmor** acts like a security guard with a strict checklist for each application: even if a public-facing service gets tricked by an exploit, AppArmor blocks it from reading files outside its allowed folders.

To enable AppArmor at boot, open `/etc/default/grub` and add the `lsm=` parameter to `GRUB_CMDLINE_LINUX_DEFAULT`:

```ini
GRUB_CMDLINE_LINUX_DEFAULT="loglevel=3 quiet lsm=landlock,lockdown,yama,integrity,apparmor,bpf"
```

Enable the AppArmor service and regenerate your GRUB configuration (AppArmor will activate on your next reboot):

```bash
sudo systemctl enable apparmor.service
sudo grub-mkconfig -o /boot/grub/grub.cfg
```

```text
Created symlink /etc/systemd/system/multi-user.target.wants/apparmor.service -> /usr/lib/systemd/system/apparmor.service.
Generating grub configuration file ...
done
```

Next, confirm that `ufw` is running with its default `deny (incoming)` policy and the LAN SSH rule we added in Step 1:

```bash
sudo ufw status verbose
```

```text
Status: active
Logging: on (low)
Default: deny (incoming), allow (outgoing), disabled (routed)
New profiles: skip

To                         Action      From
--                         ------      ----
22/tcp                     ALLOW IN    192.168.1.0/24
```

## Step 5: Sandboxing the Caddy Web Server

Before connecting our server to the internet, let's set up **Caddy** to serve our site locally with a tiny memory footprint.

First, create the web root directory and a test page:

```bash
sudo mkdir -p /var/www/yoursite
echo "<h1>Hello from the 17W NUC</h1>" | sudo tee /var/www/yoursite/index.html
```

```text
<h1>Hello from the 17W NUC</h1>
```

Replace `/etc/caddy/Caddyfile` so Caddy listens only on local loopback (`127.0.0.1:80`) and compresses responses automatically:

```caddy
http://127.0.0.1:80 {
    root * /var/www/yoursite
    file_server
    encode zstd gzip
}
```

Arch Linux's official `caddy.service` already locks down the filesystem with `ProtectSystem=strict`, `ProtectHome=true`, `PrivateDevices=true`, and `NoNewPrivileges=true`. Let's add a strict RAM cap and hide other users' processes in `/proc` by opening a systemd drop-in override:

```bash
sudo systemctl edit caddy
```

This opens an empty override file in your terminal editor (`/etc/systemd/system/caddy.service.d/override.conf`). Paste these limits and save:

```ini
[Service]
MemoryMax=128M
ProtectProc=invisible
SystemCallFilter=@system-service
```

Start Caddy and verify it responds locally:

```bash
sudo systemctl enable --now caddy
curl -s http://127.0.0.1:80
```

```text
Created symlink /etc/systemd/system/multi-user.target.wants/caddy.service -> /usr/lib/systemd/system/caddy.service.
<h1>Hello from the 17W NUC</h1>
```

Even if an attacker ever found a flaw in the web server, systemd and AppArmor keep the process trapped inside a read-only sandbox with no access to your home folder, block devices, or other processes.

## Step 6: Hosting Safely with Cloudflare Tunnel

Forwarding ports 80 and 443 on your home router is like putting your residential IP address on a highway billboard - automated scanners and botnets start rattling your doorknob within minutes.

**Cloudflare Tunnel** flips the connection around. Instead of opening incoming ports on your router, `cloudflared` dials *out* from your NUC to Cloudflare over an encrypted wire and proxies visitors straight to `http://127.0.0.1:80`.

Authenticate `cloudflared` with your Cloudflare account:

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
Tunnel credentials written to /home/eich/.cloudflared/8f3c9d12-51b4-49c1-8e2a-9b741056ef01.json.
Created tunnel nuc-web with id 8f3c9d12-51b4-49c1-8e2a-9b741056ef01
```

Copy the generated credentials file into `/etc/cloudflared/` so the system service can read it:

```bash
sudo mkdir -p /etc/cloudflared
sudo cp ~/.cloudflared/8f3c9d12-51b4-49c1-8e2a-9b741056ef01.json /etc/cloudflared/
sudo chmod 600 /etc/cloudflared/8f3c9d12-51b4-49c1-8e2a-9b741056ef01.json
```

That copies the tunnel key and locks its permissions to `root`. Next, create `/etc/cloudflared/config.yml` to map your domain to Caddy:

```yaml
tunnel: 8f3c9d12-51b4-49c1-8e2a-9b741056ef01
credentials-file: /etc/cloudflared/8f3c9d12-51b4-49c1-8e2a-9b741056ef01.json

ingress:
  - hostname: yourdomain.com
    service: http://127.0.0.1:80
  - service: http_status:404
```

Point your domain's DNS record to the tunnel, install the `cloudflared` systemd service unit, and start it:

```bash
cloudflared tunnel route dns nuc-web yourdomain.com
sudo cloudflared --config /etc/cloudflared/config.yml service install
sudo systemctl enable --now cloudflared
```

```text
Added CNAME yourdomain.com which will route to this tunnel tunnelID=8f3c9d12-51b4-49c1-8e2a-9b741056ef01
Successfully installed cloudflared.service
```

Your website is now live over HTTPS with **zero open router ports**.

## Step 7: Keeping a Rolling-Release Server Up to Date

Running a rolling-release Linux distro on a closet server is painless as long as every update has a rewind button and the small SSD never fills up.

### Automatic snapshots before every update

Because we enabled Btrfs and Snapper in Step 1, installing `snap-pac` tells `pacman` to take automatic pre- and post-upgrade snapshots whenever packages change:

```bash
sudo pacman -S snap-pac
```

```text
Packages (1) snap-pac-3.0.1-2
Total Installed Size: 0.03 MiB
```

If a kernel update ever misbehaves, you can pick the pre-update snapshot right from the GRUB boot menu and roll back in seconds.

### Checking and applying updates safely

Avoid unattended auto-upgrades on Arch. Instead, install `pacman-contrib` and run `checkupdates` to see pending patches without modifying your live package database:

```bash
sudo pacman -S pacman-contrib
checkupdates
```

```text
linux-hardened 7.2.9.hardened1-1 -> 7.2.10.hardened1-3
caddy 2.11.6-1 -> 2.11.7-1
cloudflared 2026.9.0-1 -> 2026.10.0-1
```

When you are ready to apply them, run a standard upgrade:

```bash
sudo pacman -Syu
```

```text
:: Synchronizing package databases...
 core is up to date
 extra is up to date
:: Starting full system upgrade...
resolving dependencies...
looking for conflicting packages...

Packages (3) caddy-2.11.7-1  cloudflared-2026.10.0-1  linux-hardened-7.2.10.hardened1-3

Total Installed Size:  148.20 MiB
Net Upgrade Size:        1.12 MiB

:: Proceed with installation? [Y/n]
```

### Cleaning the package cache automatically

Pacman saves every downloaded `.pkg.tar.zst` archive in `/var/cache/pacman/pkg/`. On a compact mSATA SSD, old packages will eventually eat your free space.

Enable the weekly cleanup timer (part of `pacman-contrib`) to keep only the last three versions of each package:

```bash
sudo systemctl enable --now paccache.timer
```

```text
Created symlink /etc/systemd/system/timers.target.wants/paccache.timer -> /usr/lib/systemd/system/paccache.timer.
```

### Checking if an update needs a reboot

After running `pacman -Syu`, compare the running kernel version against the installed module folder in `/usr/lib/modules`:

```bash
uname -r
ls /usr/lib/modules
```

```text
7.2.9-hardened1-1-hardened
7.2.10-hardened1-3-hardened
```

When the version in `/usr/lib/modules` is newer than `uname -r`, a kernel update was installed. Reboot the NUC, tap your YubiKey once to unlock the drive, and your sandboxed web server comes right back online.

## Summary

- **Let Archinstall 4.5 do the heavy lifting**: It detects `intel-ucode` automatically, wires `Grub` + `Snapper` into bootable recovery menus, and copies your wired network config into lightweight `systemd-networkd`.
- **Dodge the three headless traps**: Highlight `/dev/sda2` under **Disk encryption -> Partitions** so encryption actually turns on, leave **U2F login setup** blank so `sudo` never waits for a physical button press in your closet, and allow LAN SSH in the chroot before UFW blocks port 22.
- **Tune for the 2013 Celeron**: Combine Btrfs `zstd` disk compression with fast `lz4` ZRAM swap so software encryption never starves the two slow CPU cores.
- **Unlock with a tap, host without open ports**: Bind LUKS to a YubiKey (`fido2-device=auto`) for painless reboots, lock Caddy inside systemd and AppArmor sandboxes, and serve traffic outbound through Cloudflare Tunnel.
- **Upgrade with a safety net**: Use `snap-pac` for automatic pre-update snapshots and `paccache.timer` to keep your small mSATA SSD clean.

Do not toss that dusty 17-watt mini-PC into the e-waste bin - stop fighting its limits, and it will happily serve your site for years to come.

## Resources

- [Archinstall 4.5 Installer Logic (`installer.py`)](https://github.com/archlinux/archinstall/blob/78982a624824aa415f59bf88c515676a589e3c55/archinstall/lib/installer.py#L785-L1021) - Source implementation for ISO `systemd-networkd` copying, automatic `intel-ucode` detection, `mkinitcpio` FIDO2 hook generation, and `grub-btrfs` snapshot integration.
- [Archinstall 4.5 Bootloader Menu (`bootloader_menu.py`)](https://github.com/archlinux/archinstall/blob/78982a624824aa415f59bf88c515676a589e3c55/archinstall/lib/bootloader/bootloader_menu.py#L176-L182) - Source logic showing how BIOS vs. UEFI mode filters available bootloaders.
- [Archinstall 4.5 System Menu (`system_menu.py`)](https://github.com/archlinux/archinstall/blob/78982a624824aa415f59bf88c515676a589e3c55/archinstall/lib/general/system_menu.py#L54-L98) - Source definitions for the ZRAM compression algorithm selector and optional `linux-firmware` packages.
- [Archinstall 4.5 U2F PAM Handler (`authentication_handler.py`)](https://github.com/archlinux/archinstall/blob/78982a624824aa415f59bf88c515676a589e3c55/archinstall/lib/authentication/authentication_handler.py#L29-L126) - Source code showing how `U2F login setup` injects `pam_u2f.so` into `/etc/pam.d/system-login` and `/etc/pam.d/sudo`.
- [Archinstall 4.5 Firewall Application (`firewall.py`)](https://github.com/archlinux/archinstall/blob/78982a624824aa415f59bf88c515676a589e3c55/archinstall/applications/firewall.py#L43-L49) - Source code showing how selecting `ufw` enables `ufw.service` and sets `ENABLED=yes` in `/etc/ufw/ufw.conf` before first boot.
- [ArchWiki: dm-crypt and Full Disk Encryption](https://wiki.archlinux.org/title/Dm-crypt/Encrypting_an_entire_system) - Comprehensive guide to configuring LUKS block devices on Arch Linux.
- [ArchWiki: systemd-cryptenroll](https://wiki.archlinux.org/title/Systemd-cryptenroll) - Official Arch Linux guide for enrolling FIDO2 tokens into LUKS2 volumes.
- [ArchWiki: AppArmor](https://wiki.archlinux.org/title/AppArmor) - Guide to enabling the AppArmor Linux Security Module and configuring kernel boot parameters.
- [ArchWiki: System Maintenance](https://wiki.archlinux.org/title/System_maintenance) - Official guide on pacman cache maintenance, news review, and package upgrades.
- [Caddy Documentation: Caddyfile Tutorial](https://caddyserver.com/docs/caddyfile-tutorial) - Official configuration guide for serving static sites and configuring Caddy.
- [Cloudflare Tunnel: Create a Locally-Managed Tunnel (CLI)](https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/do-more-with-tunnels/local-management/create-local-tunnel/) - Official guide to authenticating, routing, and running `cloudflared` as a system service.
