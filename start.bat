:: 后台运行 bot，请先保证 go-cq 已经启动
@ECHO OFF
%1 start mshta vbscript:createobject("wscript.shell").run("""%~0"" ::",0)(window.close)&&exit
cd "%~dp0\bot"
python main.py