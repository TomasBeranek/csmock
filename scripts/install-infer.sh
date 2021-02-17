#!/usr/bin/sh

# param 1 -- name of a compiler
# param 2 -- type of a compiler for infer option --force-integration
#		-- 'cc' for C-like languages
#		-- 'javac' for Java
create_wrapper()
{
echo '#!/usr/bin/sh

compiler="'"$1"'"
compiler_original="${compiler}-original"
log_file="/builddir/infer-capture-log"
all_options="$@"
infer_dir="/builddir/infer-out"

# delete incompatible options
for arg do
  shift
  case $arg in
    -fstack-clash-protection) : ;;
       (*) set -- "$@" "$arg" ;;
  esac
done

# logging
echo -n `date +%H:%M:%S.%N` >> ${log_file}
echo " ${compiler} ${all_options}" >> ${log_file}
echo "" >> ${log_file}
echo "infer capture --reactive -o ${infer_dir} --force-integration' "$2" '-- ${compiler} $@" >> ${log_file}
echo "" >> ${log_file}
infer capture --reactive -o ${infer_dir} --force-integration' "$2" '-- ${compiler} $@ >> ${log_file} 2>&1

# a return code should be carried back to a caller
${compiler_original} ${all_options}' >> /usr/bin/$1

chmod +x /usr/bin/$1
}


log_file="/builddir/infer-capture-log"

# install Infer
cd /opt
tar -xf infer*.tar.xz -C /opt
rm infer*.tar.xz
INFER_DIR=$(ls /opt | grep infer)
ln -s /opt/${INFER_DIR}/bin/infer /usr/bin/infer

# create wrappers for compilers, this script is executed after all the dependencies are installed, 
# so all the necessary compilers should be already installed
declare -a ccompilers=(	"ack"
		      	"clang"
	      		"ccomp"
			"cproc"
			"gcc"
			"g++"
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
	if mv /usr/bin/${c} /usr/bin/${c}-original
	then
		create_wrapper ${c} cc
                echo -n `date +%H:%M:%S.%N` >> ${log_file}
                echo " /usr/bin/${c} wrapper created successfully" >> ${log_file}

	else
        	echo -n `date +%H:%M:%S.%N` >> ${log_file}
		echo " /usr/bin/${c} compiler doesn't exist" >> ${log_file}
	fi

done

for c in "${jcompilers[@]}"
do
        if mv /usr/bin/${c} /usr/bin/${c}-original
        then
                create_wrapper ${c} javac
                echo -n `date +%H:%M:%S.%N` >> ${log_file}
                echo " /usr/bin/${c} wrapper created successfully" >> ${log_file}

        else
                echo -n `date +%H:%M:%S.%N` >> ${log_file}
                echo " /usr/bin/${c} compiler doesn't exist" >> ${log_file}
        fi

done

chmod a+rw ${log_file}

