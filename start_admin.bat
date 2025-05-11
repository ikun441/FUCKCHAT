@echo off
echo 正在启动FUCKCHAT管理员后台服务...
python run_admin.py --daemon
echo 管理员后台服务已在后台启动
echo 可以通过浏览器访问 http://127.0.0.1:5004/admin 或直接访问 http://127.0.0.1:5004 来打开管理员控制台
pause 