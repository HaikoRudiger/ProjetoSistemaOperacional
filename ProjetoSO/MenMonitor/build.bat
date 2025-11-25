@echo off
echo === Compilando DLL de leitura de memória ===
gcc -shared -o memreader.dll src/c/memreader.c
move memreader.dll src/python\
echo === Concluído! ===
pause
