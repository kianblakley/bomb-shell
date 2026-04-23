<h1 align=center>bomb-shell</h1>

> [!WARNING] 
> The shell has only been tested at a resolution and scale of 1920x1080@1.0. Any other configuration is likely to have an ungodly amount of bugs at the moment. If you encounter any bugs please open a github issue.

## Installation
1. Clone and navigate to the repo:
```bash
git clone https://github.com/kianblakley/bomb-shell.git
cd bomb-shell
```
2. Create a venv and install fabric and other python dependencies:
```bash
python -m venv venv
source venv/bin/activate
pip install requirements.txt
``` 
3. Add the following keybindings to your niri `config.kdl`:
> [!NOTE]
> If you cloned the repo to any other location you will have to change the path to the venv accordingly. 
```
Mod+D {spawn-sh "~/bomb-shell/venv/bin/python -m fabric execute bombshell \"app.app_drawer.toggle()\""; }
Mod+B {spawn-sh "~/bomb-shell/venv/bin/python -m fabric execute bombshell \"app.bg_selector.toggle()\""; }
Mod+E {spawn-sh "~/bomb-shell/venv/bin/python -m fabric execute bombshell \"app.control_center.toggle()\""; }
```
4. Optionally add the following layer rules to your niri `config.kdl`:
```
layer-rule {
    match namespace="^awww-daemonoverview$"
    place-within-backdrop true
}

layer-rule {
    match namespace="^fabric$"
    background-effect {
        blur true
        xray false
    }
}
```
5. Start the awww daemon for the workspaces and overview:
```bash
awww-daemon -n workspaces
awww-daemon -n overview
```

6. Start the shell:
```bash
python main.py
```
## Autostart
> [!NOTE]
> The following section requires you to start niri with `niri-session` 


## Configuration
## Acknowledgements
[@its-darsh](https://github.com/its-darsh) and the fabric community for building fabric and helping me out on the discord  
[@Axenide](https://github.com/Axenide) for writing the upower and networking services  
[@Inparsian](https://github.com/Inparsian) for inspiring the design of the control center  



