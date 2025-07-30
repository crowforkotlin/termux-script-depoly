#!/data/data/com.termux/files/usr/bin/bash

cat > /sdcard/termux-shell.sh <<EOF
run-as com.termux files/usr/bin/bash -lic 'export PATH=/data/data/com.termux/files/usr/bin:$PATH; export LD_PRELOAD=/data/data/com.termux/files/usr/lib/libtermux-exec.so; bash -i'
EOF

echo "文件已生成到 /sdcard"
echo "\n用法说明："
echo "- 执行 sh /sdcard/termux-shell.sh 进入 termux 用户环境"
echo "注意：root 环境下 pkg 包管理器不可用，如需安装工具请先在 shell 用户环境下安装，再切换到 root 环境执行高权限操作。"

sh /sdcard/termux-shell.sh