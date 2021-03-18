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
log_file="/builddir/infer-capture-log"
ast_log_file="/builddir/infer-ast-log"
all_options="$@"
infer_dir="/builddir/infer-out"

# delete incompatible options
for arg do
  shift
  [ "$arg" = "-fstack-clash-protection" ] && continue
  [ "$arg" = "-flto=auto" ] && continue
  [ "$arg" = "-flto=jobserver" ] && continue
  [ "$arg" = "-ffat-lto-objects" ] && continue
  set -- "$@" "$arg"
done

# logging
echo -n `date +%H:%M:%S.%N` >> ${log_file}
echo " ${compiler} ${all_options}" >> ${log_file}
echo "" >> ${log_file}
echo "infer capture --reactive -o ${infer_dir} --force-integration' "$2" '-- ${compiler} $@" >> ${log_file}
echo "" >> ${log_file}
infer capture --reactive -o ${infer_dir} --force-integration' "$2" '-- ${compiler} $@ >> ${log_file} 2>&1

# save the compile command and the list of freshly captured files from infer database
echo "${compiler} $@" >> ${ast_log_file}
echo ${PWD} >> ${ast_log_file}
sqlite3 /builddir/infer-out/results.db "SELECT source_file FROM source_files WHERE freshly_captured = 1" >> ${ast_log_file}
echo "" >> ${ast_log_file}

# a return code should be carried back to a caller
${compiler_original} ${all_options}' >> /usr/bin/$1

if ! chmod +x /usr/bin/$1
then
    echo "ERROR: Failed to add +x permission to /usr/bin/$1"
    exit 1
fi
}


log_file="/builddir/infer-capture-log"

# install Infer
if ! cd /opt
then
    echo "ERROR: Failed to open /opt directory"
    exit 1
fi

if ! tar -xf $1 -C /opt
then
    echo "ERROR: Failed to extract an Infer archive $1"
    exit 1
fi

INFER_DIR=$(ls /opt | grep infer-linux | head -n 1)

if ! rm $1
then
    echo "ERROR: Failed to delete an Infer archive $1"
    exit 1
fi

if ! ln -s /opt/${INFER_DIR}/bin/infer /usr/bin/infer
then
    echo "ERROR: Failed to create a symlink to /opt/${INFER_DIR}/bin/infer"
    exit 1
fi

# test if the symlink works
if ! infer --version
then
    echo "ERROR: Failed to run a symlink to /opt/${INFER_DIR}/bin/infer"
    exit 1
fi

# create wrappers for compilers, this script is executed after all the dependencies are installed,
# so all the necessary compilers should be already installed
declare -a ccompilers=(	"ack"
		      	"clang"
	      		"ccomp"
			"cproc"
			"gcc"
			"g++"
            "c++"
			"icc"
			"icpc"
			"lcc"
			"opencc"
			"openCC"
			"pcc"
			"scc"
			"chibicc"
			"sdcc"
			"tcc"
			"vc"
			"x86_64-redhat-linux-c++"
			"x86_64-redhat-linux-g++"
			"x86_64-redhat-linux-gcc"
			"x86_64-redhat-linux-gcc-10"
			"8cc"
			"9cc"
			"lacc")

declare -a jcompilers=(	"javac")

for c in "${ccompilers[@]}"
do
	if [ -f /usr/bin/${c}-original ] || mv /usr/bin/${c} /usr/bin/${c}-original
	then
		create_wrapper ${c} cc
                echo -n `date +%H:%M:%S.%N` >> ${log_file}
                echo " /usr/bin/${c} wrapper created successfully" >> ${log_file}
	else
        	echo -n `date +%H:%M:%S.%N` >> ${log_file}
		echo " /usr/bin/${c} C/C++ compiler doesn't exist or symlink is already installed" >> ${log_file}
	fi
done

for c in "${jcompilers[@]}"
do
        if [ -f /usr/bin/${c}-original ] || mv /usr/bin/${c} /usr/bin/${c}-original
        then
                create_wrapper ${c} javac
                echo -n `date +%H:%M:%S.%N` >> ${log_file}
                echo " /usr/bin/${c} wrapper created successfully" >> ${log_file}
        else
                echo -n `date +%H:%M:%S.%N` >> ${log_file}
                echo " /usr/bin/${c} Java compiler doesn't exist or symlink is already installed" >> ${log_file}
        fi
done

if ! chmod a+rw ${log_file}
then
    echo "ERROR: Failed to add +rw permission to ${log_file}"
    exit 1
fi
