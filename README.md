<p align="center">
  <img width="300" height="300" alt="calmweb" src="https://github.com/user-attachments/assets/56e88ff3-1cb2-4263-80d0-ad7b493bb52c" />
</p>

# CalmWeb

Camlweb is a proxy acting as Web filter aimed to protect elderly or unconfident people on the internet, protecting them from ads, scams and blocking remote control software like TeamViewer.

Why use CalmWeb?
Calm Web is meant to protect people with no or poor internet knowledge.
It's aggressive by design, simple yet efficient (I hope).
It works system-wide, so no matter the browser you use, it will work and will block already installed programs or tools, even the Windows remote assistance tool!

## Installation:

Download and run CalmWeb_Setup.exe

The program will:

- Install calmweb
- Set up a firewall rule
- Add a scheduled task at startup (admin rights required to set up the proxy)
- Start the program, set up the proxy, download whitelists and blocklists

## What is allowed and what is blocked?

### By default it will block the following:

- Traffic on http port
- Browsing using IP addresses to avoid scams
- Browsing on non-standard port (80/443)
- Domains listed in those lists: All credits to them!  
   https://raw.githubusercontent.com/StevenBlack/hosts/refs/heads/master/hosts  
   https://raw.githubusercontent.com/easylist/listefr/refs/heads/master/hosts.txt  
   https://raw.githubusercontent.com/hagezi/dns-blocklists/main/domains/ultimate.txt  
   https://raw.githubusercontent.com/async-it/calmweb/refs/heads/main/filters/blocklist.txt  
   https://dl.red.flag.domains/pihole/red.flag.domains.txt  
   https://urlhaus.abuse.ch/downloads/csv/
- Domains manually added in the blocklist at %appdata%\calmweb\custom.cfg  
  <img width="668" height="17" alt="image" src="https://github.com/user-attachments/assets/01b07662-9826-4461-acd8-ae34e458ad81" />

### By default the following domains are whitelisted.

- Domains listed in those lists:  
   "https://raw.githubusercontent.com/async-it/calmweb/refs/heads/main/filters/whitelist.txt"
- Domains manually added in the whitelist at %appdata%\calmweb\custom.cfg

### Useful blocked domains:

[This list ](https://raw.githubusercontent.com/async-it/calmweb/refs/heads/main/filters/usefull_domains.txt) contains domains that may be useful if you're a "power user" but appear to be listed in blocklists.

### Known problems:

- Sandbox not working when CalmWeb is running
- Direct access to IPv6 addresses  like https://[::1]:8080

### todo / features suggestions:

- Test on Windows 10
- Allow to set up a system-wide, "discrete" mode where the program runs in the background showing no icons at all
- Add blocked domains when you discover a new scam, risky website.
- URLHaus provides URLs and IPs. For now only the domains are used and it may be more accurate to block the whole URL instead of domain in order to not block file sharing services that may be used for decent purposes.
- Show in which list a blocked or whitelisted domain appears
