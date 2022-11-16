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
        vault
        python3
        getCredsAws
      ];
    in rec {
      packages = {
        awslogin = pkgs.writeShellApplication {
          name = "awslogin";
          runtimeInputs = deps;
          text = ''
            #!${pkgs.stdenv.shell}
            ${builtins.readFile ./aws-login.sh}
          '';
        };
        cc-clone = pkgs.writeShellApplication {
          name = "cc-clone";
          runtimeInputs = deps;
          text = ''
            #!${pkgs.stdenv.shell}
            # shellcheck disable=SC2068,SC2145
            git clone codecommit::eu-central-1://codecommit-stx@$@
          '';
        };
        default = packages.awslogin;
      };
      devShell = pkgs.devshell.mkShell {
        name = "Stx";
        motd = ''
          {202}🔨 Stx shell with a bunch of cli utilities{220}
            - jq
            - terraform
            - aws cli v2
            - vault
            - git CodeCommit{reset}
          $(type -p menu &>/dev/null && menu)
        '';
        packages = deps ++ [ pkgs.starship ];
        bash.extra =''
          source <(starship init bash)
        '';
        commands = [{
          category = "Utilities";
          package = packages.awslogin;
          help =  "Helper for aws login using aws roles and Horizon";
        }{ 
          category = "Utilities";
          package = packages.cc-clone;
          help = "Git clone of code commit repo (eg: cc-clone terraform)";
        }];
      };
    }
  );
}