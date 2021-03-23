#!/bin/bash

# param 1 -- name of a compiler
# param 2 -- type of a compiler for infer option --force-integration
#		-- 'cc' for C-like languages
#		-- 'javac' for Java
create_wrapper()
{
  echo '#!/bin/bash

compiler="'"$1"'"
compiler_original="${compiler}-original"
ast_log_file="/builddir/infer-ast-log"
all_options="$@"
infer_dir="/builddir/infer-out"
skip_capture=false
lock_dir=/tmp/infer.lockdir

if [[ $# -eq 1 && "$1" == *"@/tmp/"* ]] ;
then
  skip_capture=true
  set -- "/usr/bin/${compiler_original}"
fi

for var in "$@"
do
    if [[ "$var" =~ conftest[0-9]*\.c$ ]] ;
    then
      skip_capture=true
    fi
done

if [ "${skip_capture}" = false ]
then
  # delete incompatible options
  for arg do
    shift
    [ "$arg" = "-fstack-clash-protection" ] && continue
    [ "$arg" = "-flto=auto" ] && continue
    [ "$arg" = "-flto=jobserver" ] && continue
    [ "$arg" = "-ffat-lto-objects" ] && continue
    set -- "$@" "$arg"
  done

  # locking
  while :
  do
    if mkdir "${lock_dir}" > /dev/null 2>&1
    then
      # lock acquired
      # logging
      >&2 echo ""
      >&2 echo "NOTE: INFER: ${compiler}-wrapper: running capture phase"
      if infer capture --reactive -o ${infer_dir} --force-integration' "$2" '-- ${compiler} $@ 1>&2
      then
        >&2 echo "NOTE: INFER: ${compiler}-wrapper: successfully captured: \"${compiler} $@\""
      else
        >&2 echo "WARNING: INFER: ${compiler}-wrapper: unsuccessfully captured: \"${compiler} $@\""
      fi
      >&2 echo ""

      # save the compile command and the list of freshly captured files from infer database
      echo "${compiler} $@" >> ${ast_log_file}
      echo ${PWD} >> ${ast_log_file}
      sqlite3 /builddir/infer-out/results.db "SELECT source_file FROM source_files WHERE freshly_captured = 1" >> ${ast_log_file}
      echo "" >> ${ast_log_file}

      # release lock
      rm -rf ${lock_dir}
      break
    fi
  done
fi

# a return code should be carried back to a caller
${compiler_original} ${all_options}' >> /usr/bin/$1

  if ! chmod +x /usr/bin/$1
  then
    echo "ERROR: INFER: install-infer.sh: Failed to add +x permission to /usr/bin/$1"
    exit 1
  fi
}


# install Infer
if ! cd /opt
then
  echo "ERROR: INFER: install-infer.sh: Failed to open /opt directory"
  exit 1
fi

if ! tar -xf $1 -C /opt
then
  echo "ERROR: INFER: install-infer.sh: Failed to extract an Infer archive $1"
  exit 1
fi

INFER_DIR=$(ls /opt | grep infer-linux | head -n 1)

if ! rm $1
then
  echo "ERROR: INFER: install-infer.sh: Failed to delete an Infer archive $1"
  exit 1
fi

if ! ln -s /opt/${INFER_DIR}/bin/infer /usr/bin/infer
then
  echo "ERROR: INFER: install-infer.sh: Failed to create a symlink to /opt/${INFER_DIR}/bin/infer"
  exit 1
fi

# test if the symlink works
if ! infer --version > /dev/null 2>&1
then
  echo "ERROR: INFER: install-infer.sh: Failed to run 'infer --version' to test a symlink to /opt/${INFER_DIR}/bin/infer"
  exit 1
else
  echo "NOTE: INFER: install-infer.sh: Infer installed successfully"
fi

# create wrappers for compilers, this script is executed after all the dependencies are installed,
# so all the necessary compilers should be already installed
declare -a ccompilers=( "8cc"
                        "9cc"
                        "ack"
                        "c++"
                        "ccomp"
                        "chibicc"
                        "clang"
                        "cproc"
                        "g++"
                        "gcc"
                        "icc"
                        "icpc"
                        "lacc"
                        "lcc"
                        "openCC"
                        "opencc"
                        "pcc"
                        "scc"
                        "sdcc"
                        "tcc"
                        "vc"
                        "x86_64-redhat-linux-c++"
                        "x86_64-redhat-linux-g++"
                        "x86_64-redhat-linux-gcc"
                        "x86_64-redhat-linux-gcc-10")

declare -a jcompilers=(	"javac")

for c in "${ccompilers[@]}"
do
  if [ -f /usr/bin/${c}-original ] || mv /usr/bin/${c} /usr/bin/${c}-original > /dev/null 2>&1
	then
		create_wrapper ${c} cc
    echo "NOTE: INFER: install-infer.sh: /usr/bin/${c} wrapper created successfully"
	else
		echo "NOTE: INFER: install-infer.sh: /usr/bin/${c} C/C++ compiler doesn't exist or symlink is already installed"
	fi
done

for c in "${jcompilers[@]}"
do
  if [ -f /usr/bin/${c}-original ] || mv /usr/bin/${c} /usr/bin/${c}-original > /dev/null 2>&1
  then
    create_wrapper ${c} javac
    echo "NOTE: INFER: install-infer.sh: /usr/bin/${c} wrapper created successfully"
  else
    echo "NOTE: INFER: install-infer.sh: usr/bin/${c} Java compiler doesn't exist or symlink is already installed"
  fi
done
