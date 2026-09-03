<p align="center">
  <img width="200" height="200" alt="calmweb" src="https://github.com/user-attachments/assets/56e88ff3-1cb2-4263-80d0-ad7b493bb52c" />
</p>

# Calm Web
## Français  
Calm Web agit comme un filtre web transparent, conçu pour protéger les personnes âgées ou soucieuses de la sécurité de leur navigation sur Internet. 

- Il offre une expérience plus sûre en bloquant plus de 600 000 sites publicitaires, malveillants ou de télémétrie.
- Il impose l’utilisation de la navigation sécurisée HTTPS
- Bloque les [logiciels de contrôle à distance](https://github.com/async-it/calmweb/blob/main/filters/blocklist.txt) courants ainsi que diverses techniques fréquemment utilisées à des fins malveillantes.

Installé au niveau du système, il protège tous les utilisateurs et navigateurs, même futurs.

⚠️ Calm Web n'est pas un anti-virus et ne garantit en aucun cas une protection totale contre le piratage ou les arnaques, et ne prétend pas le faire. Chaque utilisateur reste responsable de sa navigation et doit être conscient des risques encourus.
Toutefois, CalmWeb permet de réduire certains risques en ajoutant un garde-fou : il bloque des techniques connues en se basant sur des ressources communautaires.

### Installation
Télécharger la dernière version de Calm Web pour Windows uniquement [TELECHARGEMENT](https://github.com/async-it/calmweb/releases/download/1.5.5/CalmWeb_Setup_1.5.5.exe)  
Executer le fichier téléchargé et suivre les indications  
Calm Web Démarre dans la barre de tâches (il peut être nécéssaire de cliquer sur <img width="32" height="27" alt="image" src="https://github.com/user-attachments/assets/20bafe23-b3ca-411e-8706-922b123859b2" /> situé en bas à droite)
)  

### Fonctionnement technique

Calm Web démarre un [proxy](https://fr.wikipedia.org/wiki/Proxy) local sur le PC et configure Windows pour en forcer l’utilisation afin d’accéder à Internet.
Il ne brise pas les connexion sécurisées d'origine et n'installe pas de certificats tiers.

Lors de son démarrage, Calm Web télécharge diverses listes de blocage et ajoute tous les domaines trouvés dans une liste noire, empêchant ainsi la navigation vers ceux-ci.

Par défaut, il :
- Bloque tous les domaines listés, sauf ceux préconfigurés dans une liste blanche
- Bloque les outils de « support à distance » régulièrement utilisés à mauvais escient
- Bloque la navigation HTTP afin de garantir une navigation sécurisée
- Bloque l’accès direct aux adresses IP
- Bloque l’utilisation de ports non standards

### Utilisation
Une fois installé, CalmWeb peut être oublié.

**Un double-clic sur l'icône ouvre la fenêtre Calm Web**, qui regroupe tout ce dont on peut avoir besoin :

| Page | Contenu |
| --- | --- |
| **État** | Protection active ou non, gros bouton pour l'activer / la désactiver, nombre de sites bloqués et autorisés, taille des listes, dernière mise à jour, connexions en cours |
| **Activité** | Journal en direct, coloré, filtrable (bloqués / autorisés / système), recherche par domaine et export dans un fichier texte |
| **Paramètres** | Interrupteurs pour chaque règle de filtrage, choix de la langue (français / anglais) et du thème (système, clair, sombre) |
| **Listes** | Édition de la liste blanche et de la liste noire locale, et surtout : « **Vérifier un domaine** », qui répond si un domaine est bloqué **et par quelle liste** |
| **À propos** | Version, recherche de mise à jour, emplacement du fichier de configuration |

L'interface suit la langue de Windows au premier démarrage et peut être changée à tout moment dans *Paramètres*.

> **Débloquer un site.** Les listes noires sont *téléchargées* : la plupart des domaines bloqués (`teamviewer.com`, par exemple) ne se trouvent pas dans votre configuration, et les retirer de votre liste noire locale ne change donc rien. Le seul moyen de rouvrir un domaine est de l'ajouter à la **liste blanche**, qui a la priorité sur toutes les autres règles. La page *Listes → Vérifier un domaine* indique de quelle liste vient le blocage et propose un bouton **Autoriser ce site** qui s'applique immédiatement. Le journal d'activité distingue lui aussi « liste noire téléchargée » de « votre liste noire ».

Le clic droit sur l'icône reste disponible et donne les mêmes actions en raccourci : état et compteurs, activation / désactivation, interrupteurs de filtrage, édition du fichier de configuration, rechargement des listes, mise à jour, quitter.

Après toute modification, pensez à recharger la configuration.
Certains sites web conservent du cache ou des connexions ouvertes : en cas de doute, redémarrez le PC.

### Versions HTTP, HTTP/2 et HTTP/3 (QUIC)

Calm Web se place entre le navigateur et Internet, et doit donc suivre les protocoles réellement utilisés aujourd'hui :

- **HTTP/1.1** — les requêtes en clair sont analysées, filtrées puis relayées. Les en-têtes « hop-by-hop » sont retirés, `Expect: 100-continue` est laissé au serveur d'origine, et la négociation `Upgrade` est préservée pour que les **WebSockets** continuent de fonctionner.
- **HTTP/2** — négocié par ALPN *à l'intérieur* de TLS : il traverse le tunnel `CONNECT` sans être touché. Le relais ne fait aucune hypothèse sur le découpage des messages et tolère les longues périodes d'inactivité, une connexion HTTP/2 étant volontairement maintenue ouverte entre deux requêtes.
- **HTTP/3 (QUIC)** — QUIC circule sur UDP et ne peut pas passer par un proxy `CONNECT`. Tous les navigateurs courants détectent le proxy système et **retombent d'eux-mêmes sur HTTP/2 en TCP**, donc filtré. Le cas restant est celui d'un logiciel qui ignore le proxy : l'option `block_quic` ajoute alors une règle de pare-feu bloquant UDP 443/80, ce qui rend ce repli obligatoire. Elle est **désactivée par défaut** (elle demande les droits administrateur) et la règle est retirée à l'arrêt de Calm Web.

### Test:
Envie de constater l'efficacité?
[Activer calmweb et rendez-vous ici](https://paileactivist.github.io/toolz/adblock.html)


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

**Double-clicking the tray icon opens the Calm Web window**, which holds everything an advanced user needs: a **Status** page (protection on/off with a single large button, blocked and allowed counters, list sizes, live connections), a live colour-coded **Activity** log with category filters, domain search and text export, a **Settings** page with a switch per rule plus language (French/English) and theme (system/light/dark), a **Lists** page to edit the whitelist and the local blocklist — including a *Check a domain* box that says whether a domain is blocked **and which list it came from** — and an **About** page with the version and update check.

The interface follows the Windows language on first run and can be changed at any time in *Settings*.

> **Unblocking a site.** The blocklists are *downloaded*: most blocked domains (`teamviewer.com`, for instance) are not in your configuration at all, so removing them from your own blocklist changes nothing. The only way to reopen a domain is to add it to the **whitelist**, which takes priority over every other rule. *Lists → Check a domain* names the list responsible and offers an **Allow this site** button that takes effect immediately. The activity log likewise distinguishes "downloaded blocklist" from "your blocklist".

Right-clicking the icon still works and mirrors the same actions: state and counters, enable/disable, one switch per filtering rule, edit the configuration file, reload the lists, check for updates, quit.

After making any changes, remember to reload the configuration.
Some websites retain cached data or open connections: if in doubt, restart your PC.

### HTTP versions, HTTP/2 and HTTP/3 (QUIC)

- **HTTP/1.1** — cleartext requests are parsed, filtered and forwarded. Hop-by-hop headers are stripped, `Expect: 100-continue` is left to the origin server, and `Upgrade` handshakes are preserved so **WebSockets** keep working.
- **HTTP/2** — negotiated by ALPN *inside* TLS, so it rides through the `CONNECT` tunnel untouched. The relay makes no assumption about message framing and tolerates long idle periods, since an h2 connection is deliberately kept open between requests.
- **HTTP/3 (QUIC)** — QUIC runs over UDP and cannot travel through a `CONNECT` proxy. Every mainstream browser sees the system proxy and **falls back to HTTP/2 over TCP on its own**, where CalmWeb filters it. For the rare application that ignores the proxy, the `block_quic` option adds a firewall rule blocking outbound UDP 443/80 so that fallback becomes mandatory. It is **off by default** (it needs administrator rights) and the rule is removed when CalmWeb exits.


## Block lists:
https://raw.githubusercontent.com/StevenBlack/hosts/refs/heads/master/hosts  
https://raw.githubusercontent.com/easylist/listefr/refs/heads/master/hosts.txt  
https://raw.githubusercontent.com/hagezi/dns-blocklists/main/domains/ultimate.txt  
https://raw.githubusercontent.com/async-it/calmweb/refs/heads/main/filters/blocklist.txt  
https://dl.red.flag.domains/pihole/red.flag.domains.txt  
https://urlhaus.abuse.ch/downloads/csv/  

## Whitelist:
https://raw.githubusercontent.com/async-it/calmweb/refs/heads/main/filters/whitelist.txt

## Configuration (`custom.cfg`, section `[OPTIONS]`)

| Option | Default | Effect |
| --- | --- | --- |
| `block_http_traffic` | `1` | Forces HTTPS. Also refuses `CONNECT` to port 80, which would otherwise tunnel cleartext HTTP past this rule. |
| `block_ip_direct` | `1` | Blocks browsing straight to an IP address (IPv4 and IPv6). |
| `block_http_other_ports` | `1` | Only 80, 443 and the VoIP/STUN ports are allowed. Set to `0` if a sandbox or business application stops working. |
| `allow_revocation_http` | `1` | Lets certificate revocation traffic (CRL, AIA, OCSP) through the HTTPS-only rule; these only ever travel over cleartext HTTP. No switch in the interface — set it here. Each request it allows appears in the *System* tab. The blocklist still applies. |
| `ask_elevation` | `1` | Offer a restart as administrator at startup, and only when that would achieve something — today, installing the loopback exemptions. Declining starts CalmWeb unprivileged. Set to `0` on an account that can never elevate, so the prompt stops coming. |
| `block_quic` | `0` | Firewall rule blocking outbound UDP 443/80 so HTTP/3 must fall back to filtered TCP. Needs administrator rights. |
| `language` | *(empty)* | `fr`, `en`, or empty to follow Windows. |
| `theme` | `system` | `system`, `light` or `dark`. |

Every option is also available from the window (*Settings*) and from the tray menu, and is written back to `custom.cfg` when changed.

### Building

`scripts\build.cmd` builds the executable with PyInstaller and then the installer with Inno Setup.

**PyInstaller 6.22 or newer is required.** Python 3.14 ships Tcl/Tk 9, whose library lives in a zipfs archive inside the DLL instead of a folder on disk (`$tcl_library` reads `//zipfs:/lib/tcl/tcl_library`). Earlier PyInstaller releases cannot bundle it: the build succeeds, but the frozen application fails at startup with `FileNotFoundError: Tcl data directory "..._MEIxxxxx\_tcl_data" not found`. Upgrade with `python -m pip install --upgrade pyinstaller`. The build script prints which case it detected.

### Known problems:

- Sandbox not working when CalmWeb is running by default due to port block
  Set "block_http_other_ports" to "0"

### todo / features suggestions:

- Test on Windows 10
- Allow to set up a system-wide, "discrete" mode where the program runs in the background showing no icons at all
- Add blocked domains when you discover a new scam, risky website.
- URLHaus provides URLs and IPs. For now only the domains are used and it may be more accurate to block the whole URL instead of domain in order to not block file sharing services that may be used for decent purposes.

### Fixed in 1.7.0

- CalmWeb now offers to restart itself as administrator, and only when there is something
  to gain from it: elevation buys exactly one thing, the loopback exemptions, so once those
  are in place the question stops being asked and an unprivileged start is normal and
  silent. A UAC prompt at every launch, for nothing, is how people learn to click through
  UAC prompts. Declining is an answer rather than an error — CalmWeb starts without
  privileges, which costs only those exemptions, and says so in the *System* tab. The offer
  is made before the single-instance lock is taken, because an elevated copy would
  otherwise find the lock held by the unprivileged one it is replacing.

- When the loopback exemptions cannot be installed for want of administrator rights,
  CalmWeb now raises a desktop notification rather than only a log line. The activity feed
  is no help to someone whose Outlook will not open: they are not looking at CalmWeb, they
  are looking at an application that does nothing. Unlike block notifications this one does
  not depend on `notify_on_block` — it is not a filtering decision but a total blackout,
  and it is announced once per run however often the proxy is toggled.

- The new Outlook for Windows and the new Teams are packaged applications, isolated in
  their entirety rather than only at their sign-in step. With the proxy on and no loopback
  exemption they have no network at all and simply never open. Both package families are
  now exempted alongside the authentication brokers, and the result — already in place,
  added, refused, or blocked for want of administrator rights — is recorded in the *System*
  tab, because this is the one failure that leaves no other trace anywhere.

- The proxy could go deaf without saying so. The accept loop ran in a bare thread with no
  error handling: one exception and it was gone for the rest of the session, while the
  listening socket stayed open and the tray still reported the proxy as active. New
  connections then piled into the operating system's backlog until it was full and were
  dropped **without a reset** — the client sees a SYN that is never answered, retries for
  about six seconds and reports that it cannot connect, with nothing in the CalmWeb log to
  match, because nothing ever reached CalmWeb. The loop is now supervised and restarted,
  and a watchdog completes a real TCP handshake on the listening port every 15 seconds:
  two consecutive failures rebuild the server. Every step is recorded in the *System* tab.
- Idle tunnels no longer wake once a second. Each open tunnel is a thread, and at a few
  hundred of them the wake-ups alone take enough of the interpreter to starve the accept
  loop. Idleness is now measured against the clock rather than counted in ticks, so the
  poll interval could be raised to 5 seconds without shortening `TUNNEL_IDLE_TIMEOUT`.
- The listen backlog went from 128 to 512, so a burst of connections is queued rather than
  dropped while the accept loop catches up.

- Certificate revocation over HTTP is now handled in two layers instead of one. The
  certificate authorities are named in the whitelist — which is narrow and needs no
  heuristic — and `allow_revocation_http` stays behind them for the ones no list knows
  about: an enterprise CA on an intranet, a regional authority, a CRL that moved hostname.
  Missing one is not a loud failure, validation just stalls with nothing in the logs, so
  the safety net is worth keeping. Its switch has left the window and the tray menu: it is
  a diagnostic step, not a decision to put in front of someone, so it lives in `custom.cfg`
  alone. Everything it lets through is recorded in the *System* tab of the activity feed,
  naming the host — an exception with no visible switch has to stay auditable.

- Outlook stuck on "loading profile", or connected but no longer synchronising, while the
  proxy is on. Office signs in through the Windows Web Account Manager, whose broker runs
  in an AppContainer, and Windows forbids AppContainer processes from reaching `127.0.0.1`
  — the connection is refused by the OS before it ever reaches CalmWeb, which is why
  nothing appeared in the logs. The brokers are now exempted (`CheckNetIsolation
  LoopbackExempt`) when the proxy is switched on, and the exemption is withdrawn when it is
  switched off. Adding one needs administrator rights: without them CalmWeb now says so and
  prints the command to run, instead of leaving an invisible failure.
- Long-lived connections cut after ten idle minutes. `TUNNEL_IDLE_TIMEOUT` is now 30
  minutes, the floor Microsoft documents for a proxy in front of Exchange: Outlook keeps
  its notification channel open and silent between events, so the old value severed it
  mid-session and the mailbox reported it had not updated in a while.

### Fixed in 1.6.0

- Direct access to IPv6 addresses such as `https://[::1]:8080` — the `CONNECT` authority parser now handles bracketed IPv6 literals, so those requests are filtered instead of slipping through.
- Showing which list a blocked or whitelisted domain comes from — see *Lists → Check a domain*.
