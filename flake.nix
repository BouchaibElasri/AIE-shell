{
  description = "Stx shell helper";

  inputs = {
    nixpkgs.url = "github:nixos/nixpkgs/nixos-unstable";
    flake-utils.url = "github:numtide/flake-utils/master";
    devshell.url = "github:numtide/devshell/master";
  };
  nixConfig.bash-prompt = "\\e[0;32m[\\u@stx] \\W>\\e[m ";

  outputs = { self, nixpkgs, flake-utils, devshell }:
    flake-utils.lib.eachDefaultSystem (system:
    let 
      pkgs = import nixpkgs {
          inherit system;
          overlays = [ devshell.overlay ];
        };
      getCredsAws = pkgs.writers.writePython3Bin "get_creds_aws" {
          libraries = with pkgs.python310Packages; [ boto3 boto requests beautifulsoup4 ];
          flakeIgnore = [ "E231" "E265" "E275" "E501" "F401" "W291" ];
        } "${builtins.readFile ./getcreds.aws.py}";
      deps = with pkgs; [
        coreutils
        awscli2
        jq
        git
        git-remote-codecommit
        terraform
        openssh
        groff
        unzip
        sudo
        vault
        python3
        getCredsAws
      ];
    in rec {
      packages.default = pkgs.writeShellApplication {
        name = "awslogin";
        runtimeInputs = deps;
        text = ''
          #!${pkgs.stdenv.shell}
          ${builtins.readFile ./aws-login.sh}
        '';
      };
      devShell = pkgs.devshell.mkShell {
        name = "Secutix CE";
        packages = deps ++ [ pkgs.starship ];
        bash.extra =''
          source <(starship init bash)
        '';
        commands = [{ 
          category = "login";
          # description =  "Helper for aws login using aws roles and Horizon";
          name = "awslogin";
          command = "${builtins.readFile ./aws-login.sh}";
        }{ 
          category = "git";
          name = "cc-clone";
          # description = "Git clone of code commit repo (eg: cc-clone terraform)";
          command = "git clone codecommit::eu-central-1://codecommit-stx@$@";
        }];
      };
    }
  );
}