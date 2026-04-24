<h1 align=center>bomb-shell</h1>

> [!WARNING] 
> The shell is currently in alpha and may not be stable. If you encounter any bugs please open a GitHub issue.

![Screenshot](assets/1.png)


## Dependencies:
| Dependency | Used For | Installation |
| --- | --- | --- |
| `niri` | Window manager | [niri](https://niri-wm.github.io/niri/Getting-Started.html) |
| `fabric` | GUI toolkit | [fabric](https://wiki.ffpy.org/getting-started/installation-guide/) |
| `awww` | Wallpaper daemon | [awww](https://codeberg.org/LGFae/awww) |

## Installation:

1. Install dependencies for your distribution using the links above.
> [!TIP] 
> Fabric's python package is already included in this project's requirements.txt, you only need to install Fabric's system dependencies to avoid installing twice.

2. Clone and navigate to the repo:
```bash
git clone https://github.com/kianblakley/bomb-shell.git
cd bomb-shell
```
3. Create a venv and install python dependencies:
```bash
python -m venv venv
source venv/bin/activate
pip install requirements.txt

``` 
4. Add the following keybindings to your niri `config.kdl`:
> [!TIP]
> Adjust the path `~/bomb-shell/venv/bin/python` accordingly. 
```
Mod+D {spawn-sh "~/bomb-shell/venv/bin/python -m fabric execute bombshell \"app.app_drawer.toggle()\""; }
Mod+B {spawn-sh "~/bomb-shell/venv/bin/python -m fabric execute bombshell \"app.bg_selector.toggle()\""; }
Mod+E {spawn-sh "~/bomb-shell/venv/bin/python -m fabric execute bombshell \"app.control_center.toggle()\""; }
```
5. Add the following layer rules to your niri `config.kdl`:
```
layer-rule {
    match namespace="^awww-daemonoverview$"
    place-within-backdrop true
}

// Optional if you wish to enable blur for the shell
layer-rule {
    match namespace="^fabric$"
    background-effect {
        blur true
        xray false
    }
}
```
6. Start the awww daemon for the workspaces and overview:
```bash
awww-daemon -n workspaces
awww-daemon -n overview
```

7. Start the shell:
```bash
python main.py
```
## Autostart:
The following section requires you to start niri with `niri-session` or equivalent, see [here](https://niri-wm.github.io/niri/Example-systemd-Setup.html) for more details.
1. Create a systemd user configuration folder if it doesn't exist already:
```bash
mkdir -p ~/.config/systemd/user
```
2. Copy the `.service` files for `awww` and `bombshell` to the systemd config folder:
```bash
cp ~/bomb-shell/systemd/* ~/.config/systemd/user
```
3. Link the services to niri: 
```bash
systemctl --user add-wants niri.service bombshell.service
systemctl --user add-wants niri.service awww@workspaces.service
systemctl --user add-wants niri.service awww@overview.service
```

Alternatively, add the following lines to your niri `config.kdl`:
```bash
spawn-sh-at-startup "awww-daemon -n workspaces"
spawn-sh-at-startup "awww-daemon -n overview"
spawn-sh-at-startup "~/bomb-shell/venv/bin/python main.py"
```
## Configuration:

## Acknowledgements:
[@its-darsh](https://github.com/its-darsh) and the fabric community for building fabric and helping me out on the discord  
[@Axenide](https://github.com/Axenide) for writing the upower and networking services  
[@Inparsian](https://github.com/Inparsian) for inspiring the design of the control center  



