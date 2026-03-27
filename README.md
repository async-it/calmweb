<p align="center">
  <img width="200" height="200" alt="calmweb" src="https://github.com/user-attachments/assets/56e88ff3-1cb2-4263-80d0-ad7b493bb52c" />
</p>

# CalmWeb
## Français  
CalmWeb fait office de filtre web transparent, forçant une navigation sécurisée en bloquant plus de 600 000 sites web publicitaires et malveillants. Il impose également la navigation sécurisée HTTPS et bloque diverses techniques régulièrement utilisées à mauvais escient.

Installé au niveau du système, il protège tous les navigateurs et bloque les éventuels logiciels de contrôle à distance qui pourraient déjà être installés.

⚠️ CalmWeb ne garantit en aucun cas une protection totale contre le piratage ou les arnaques, et ne prétend pas le faire. Chaque utilisateur reste responsable de sa navigation et doit être conscient des risques encourus.
Toutefois, CalmWeb permet de réduire certains risques en ajoutant un garde-fou : il bloque des techniques connues en se basant sur des ressources communautaires.

### Fonctionnement technique

CalmWeb démarre un proxy local sur le PC et configure Windows pour en forcer l’utilisation afin d’accéder à Internet.
Il télécharge diverses listes de blocage et ajoute tous les domaines trouvés dans une liste noire, empêchant ainsi la navigation vers ceux-ci.

Par défaut, il :
- bloque tous les domaines listés, sauf ceux préconfigurés dans une liste blanche
- bloque les outils de « support à distance » régulièrement utilisés à mauvais escient
- bloque la navigation HTTP afin de garantir une navigation sécurisée
- bloque l’accès direct aux adresses IP
- bloque l’utilisation de ports non standards

### Utilisation
Une fois installé, CalmWeb peut être oublié.

Si vous êtes un utilisateur avancé ou si vous pensez qu’il interfère avec le bon fonctionnement de votre système, tous les paramètres de CalmWeb sont modifiables.
En faisant un clic droit sur son icône, vous pouvez :
- Afficher le journal afin de voir quels sites sont bloqués ou autorisés
- Quitter ou désactiver CalmWeb afin de rétablir un accès à Internet non filtré
- Editer le fichier de configuration pour
- Autoriser la navigation HTTP, l’accès direct aux IP ou l’utilisation de ports alternatifs
- Ajouter des entrées à la liste blanche (par exemple pour autoriser un logiciel de contrôle à distance spécifique)
- Ajouter d’autres domaines à la liste noire.

Après toute modification, pensez à recharger la configuration.
Certains sites web conservent du cache ou des connexions ouvertes : en cas de doute, redémarrez le PC.


# English
CalmWeb acts as a transparent web filter, forcing secure browsing by blocking over 600,000 advertising and malicious websites. It also enforces HTTPS secure browsing and blocks various techniques commonly used without proper knowledge.

Installed at the system level, it protects all browsers and blocks any remote control software that may already be installed.

### How it works
CalmWeb starts a local proxy on the PC and configures Windows to force its use for internet access.

It downloads various blocklists and adds all found domains to a blacklist, thus blocking browsing to them.

By default, it:
- blocks all listed domains except those pre-configured in a whitelist
- blocks "remote support" tools that are frequently misused
- blocks HTTP browsing to ensure secure browsing
- blocks direct access to IP addresses
- blocks the use of non-standard ports

### Usage
Once installed, CalmWeb can be left alone.

If you are an advanced user or if you believe it is interfering with your system's proper functioning, all CalmWeb settings are customizable.
By right-clicking its icon, you can:
- View the log to see which sites are blocked or allowed
- Exit or disable CalmWeb to restore unfiltered internet access
- Edit the configuration file to:
- Allow HTTP browsing, direct IP access, or the use of alternative ports
- Add entries to the whitelist (for example, to allow specific remote control software)
- Add other domains to the blacklist.

After making any changes, remember to reload the configuration.
Some websites retain cached data or open connections: if in doubt, restart your PC.


## Block lists:
https://raw.githubusercontent.com/StevenBlack/hosts/refs/heads/master/hosts  
https://raw.githubusercontent.com/easylist/listefr/refs/heads/master/hosts.txt  https://raw.githubusercontent.com/hagezi/dns-blocklists/main/domains/ultimate.txt  
https://raw.githubusercontent.com/async-it/calmweb/refs/heads/main/filters/blocklist.txt  
https://dl.red.flag.domains/pihole/red.flag.domains.txt  
https://urlhaus.abuse.ch/downloads/csv/

## Whitelist:
https://raw.githubusercontent.com/async-it/calmweb/refs/heads/main/filters/whitelist.txt


### Known problems:

- Sandbox not working when CalmWeb is running
- Direct access to IPv6 addresses  like https://[::1]:8080

### todo / features suggestions:

- Test on Windows 10
- Allow to set up a system-wide, "discrete" mode where the program runs in the background showing no icons at all
- Add blocked domains when you discover a new scam, risky website.
- URLHaus provides URLs and IPs. For now only the domains are used and it may be more accurate to block the whole URL instead of domain in order to not block file sharing services that may be used for decent purposes.
- Show in which list a blocked or whitelisted domain appears
