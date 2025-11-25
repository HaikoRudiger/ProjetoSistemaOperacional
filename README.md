# 🖥️ Monitor de Memória Virtual – Projeto de Sistemas Operacionais

Este projeto implementa um monitor completo de memória virtual no Windows, exibindo informações em tempo real sobre:

✔️ Page Faults (totais e delta)  
✔️ Uso de Swap  
✔️ Fragmentação de memória virtual  
✔️ Resumo da memória (Commit / Reserve / Free)  
✔️ Visualização gráfica interativa com Matplotlib  
✔️ Leitura direta da memória usando DLL escrita em C  

Toda a interface foi desenvolvida em **Tkinter + Matplotlib**, e a leitura dos dados é feita via uma **DLL (memreader.dll)** escrita em C usando APIs nativas do Windows:
- OpenProcess
- VirtualQueryEx
- GetProcessMemoryInfo

---

## 📥 1. Clonar o Repositório no terminal
git clone https://github.com/HaikoRudiger/ProjetoSistemaOperacional.git  
cd ProjetoSistemaOperacional

---

## 🧰 2. Abrir o Projeto no VS Code

Abra o Visual Studio Code (IDE recomendada para o projeto).

➡️ **Recomendação:** execute o VS Code **como Administrador**  
Isso garante um melhor acesso aos processos do Windows, evitando erros de permissão ao ler memória via DLL.

---

## 📦 3. Instalar Dependências

O projeto utiliza **Matplotlib** para gerar gráficos (Top5 Page Faults, gráficos individuais, fragmentação visual).

Instale as dependências pelo terminal integrado do VS Code:
**pip install matplotlib**

Caso deseje garantir compatibilidade com o Tkinter (geralmente já incluído no Python do Windows):
pip install tk

---

## ▶️ 4. Executar o Projeto

No terminal integrado do VS Code, execute:
**python main.py**

Se tudo estiver correto, a janela principal do **Monitor de Memória** será aberta automaticamente.

---

## 🧪 5. Funcionalidades Principais

### 🔹 Monitor de Processos
- Lista todos os processos do Windows via tasklist
- Permite pesquisar, selecionar e analisar um processo individual

### 🔹 Page Faults em Tempo Real
- Mostra page faults totais e delta por processo
- Exibe Top 5 processos com maior variação
- Gráficos atualizados automaticamente
- Gráfico individual para análise detalhada

### 🔹 Uso de Swap
- Exibe quanto cada processo moveu para memória secundária
- Usa a função da DLL obter_swap_mb()

### 🔹 Fragmentação de Memória
- Lê a memória virtual completa via DLL em C
- Lista cada bloco (endereço base, tamanho, estado)
- Gera mapa visual mostrando:
  - Commit
  - Reserve
  - Free
- Permite definir quantos blocos exibir
- Botão para limpar o gráfico

### 🔹 Resumo de Memória (Commit / Reserve / Free)
- Mostra painel gráfico com percentuais e valores em MB

---

## 🧩 6. Arquitetura Interna

**Python (Tkinter + Matplotlib)**  
→ Interface gráfica, gráficos e lógica principal

**DLL em C**  
→ Leitura de memória, processos, swap e fragmentação

**Comunicação via ctypes**

---

## 📝 7. Requisitos

- Windows 10 ou 11  
- Python 3.10+  
- Visual Studio Code (opcional, mas recomendado)  
- Execução como Administrador (recomendado)

---

## 👥 Autores
**Beatriz Moresco Joaquim e Haiko Rüdiger.**

Projeto desenvolvido para a disciplina de **Sistemas Operacionais**, com foco em memória virtual, paginação e gestão de processos.
