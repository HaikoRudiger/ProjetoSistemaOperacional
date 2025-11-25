#ordem Python → DLL → Código C → DLL → Python
import tkinter as tk
from tkinter import ttk, messagebox
# chama as funções do C 
from ctypes import (
    # CDLL, o python ganha permissão para acessar as funções
    # c_uint32 passa o PID para DLL
    CDLL, c_uint32, Structure, c_double, c_ulong,
    c_ulonglong, POINTER, c_int
)
import subprocess
import os
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure
from matplotlib.colors import ListedColormap

MEM_COMMIT  = 0x1000
MEM_RESERVE = 0x2000
MEM_FREE    = 0x10000

class MemResumo(Structure):
    _fields_ = [
        ("commitMB",  c_double),
        ("reserveMB", c_double),
        ("freeMB",    c_double)
    ]


class MemBloco(Structure):
    _fields_ = [
        ("baseAddress", c_ulonglong),
        ("regionSize",  c_ulonglong),
        ("state",       c_ulong),
    ]

# Carregar DLL
# Como conversar com o C
dll_path = os.path.join(os.path.dirname(__file__), "memreader.dll")
dll = CDLL(dll_path)
dll.listar_resumo.restype = MemResumo
dll.obter_page_faults.restype = c_ulong
dll.obter_swap_mb.restype = c_double

dll.listar_fragmentacao.argtypes = [c_uint32, POINTER(MemBloco), c_int]
dll.listar_fragmentacao.restype  = c_int

# Page Faults
pid_resumo_atual = None
nome_resumo_atual = None
widgets_resumo = {}

tracked_pf = None
history_pf = {}     # histórico usado pelo TOP 5
ultimos_pfs = {}    # usado pelo TOP 5 para calcular delta

MAX_PF_POINTS = 10 # os ultimos 10 deltas medidos

MAX_BLOCOS_FRAG = 4096

janelas_individuais = {} # armazena as janelas em si Janelas individuais abrir_grafico_individual(), fechar_grafico_individual() e atualizar_pf_individual()

spin_blocos_frag = None # Spinbox da quantidade de blocos do mapa de fragmentação (lido na hora de desenhar o gráfico)

# ABA 1 ------ Funções da primeira aba "Monitor de memoria"
def listar_processos(filtro=None):
    tabela.delete(*tabela.get_children())
    result = subprocess.run(["tasklist"], capture_output=True, text=True)
    linhas = result.stdout.splitlines()

    for linha in linhas[3:]:
        if not linha.strip():
            continue
        cols = linha.split()
        if len(cols) < 2 or not cols[1].isdigit():
            continue

        nome = cols[0]
        pid = cols[1]

        #verifica se não foi digitado nada na pesquisa e mostra todos os processos utilizado para o botão listar todos
        if filtro and filtro.lower() not in nome.lower():
            continue

        tabela.insert("", "end", values=(pid, nome))

# responsavel por pegar o processo selecionado na tabela e pedir ao C o resumo de memoria e iniciar o monitoramento continuo de 1s e atualizar as barras
def analisar_processo():
    global pid_resumo_atual, nome_resumo_atual, widgets_resumo

    try:
        item = tabela.selection()[0]
    except:
        messagebox.showwarning("Atenção", "Selecione um processo!")
        return

    pid = int(tabela.item(item, "values")[0])
    nome = tabela.item(item, "values")[1]

    # atualiza os valores globais
    pid_resumo_atual = pid
    nome_resumo_atual = nome
    widgets_resumo.clear() # limpa quando chama outro processo

    # python chama o DLL e a DLL chama a função C listar_resumo(pid) envia as informações e o C retorna com os dados
    resumo = dll.listar_resumo(c_uint32(pid))
    mostrar_resumo_inline(pid, nome, resumo)

    iniciar_atualizacao_resumo()


def pesquisar():
    texto = entrada_pesquisa.get().strip()
    listar_processos(texto if texto else None)

# cria as barras, atualiza as barras e mostra os textos, é chamado toda vez que um processo é selecionado
# recebe os pid, nome e resumo(commitMB, reserveMB e freeMB)
def mostrar_resumo_inline(pid, nome, resumo):
    global widgets_resumo

    total = resumo.commitMB + resumo.reserveMB + resumo.freeMB
    # se ficar zero, processo fechou ou DLL não conseguiu ler ou erro de permissão
    if total <= 0:
        # então ele apaga tudo e mostra "erro ao ler memoria" e sai da funcao
        for w in frame_resumo.winfo_children():
            w.destroy()
        tk.Label(frame_resumo, text="Erro ao ler memória.", fg="red").pack()
        return

     # Criar widgets só uma vez
    if not widgets_resumo:
        for w in frame_resumo.winfo_children():
            w.destroy()

        titulo = tk.Label(frame_resumo, font=("Segoe UI", 10, "bold"))
        titulo.pack(pady=5)

        def criar_barra(nome, cor):
            frame = tk.Frame(frame_resumo)
            frame.pack(pady=3)

            lbl = tk.Label(frame, width=22, anchor="w")
            lbl.pack(side=tk.LEFT)

            style = ttk.Style()
            style.configure(f"{nome}.bar.Horizontal.TProgressbar",
                            troughcolor="#f2f2f2",
                            background=cor)

            pb = ttk.Progressbar(frame,
                                 length=200,
                                 style=f"{nome}.bar.Horizontal.TProgressbar",
                                 maximum=100)
            pb.pack(side=tk.LEFT, padx=10)
            return lbl, pb

        lbl_commit, pb_commit = criar_barra("Commit", "#4CAF50")
        lbl_reserva, pb_reserva = criar_barra("Reserva", "#2196F3")
        lbl_livre, pb_livre     = criar_barra("Livre",  "#9E9E9E")

        lbl_total = tk.Label(frame_resumo, font=("Segoe UI", 9, "italic"))
        lbl_total.pack(pady=5)

        # guarda referencia de todos os widgets criados para não ficar recriando
        # se não ia ficar piscando na tela toda vez recriado
        widgets_resumo = {
            "titulo":      titulo,
            "lbl_commit":  lbl_commit,  "pb_commit":  pb_commit,
            "lbl_reserva": lbl_reserva, "pb_reserva": pb_reserva,
            "lbl_livre":   lbl_livre,   "pb_livre":   pb_livre,
            "lbl_total":   lbl_total,
        }

    #atualização dos textos
    widgets_resumo["titulo"].config(text=f"Resumo de Memória – {nome} (PID {pid})")

    widgets_resumo["lbl_commit"].config(text=f"Commit: {resumo.commitMB:.2f} MB")
    widgets_resumo["pb_commit"].config(value=(resumo.commitMB / total) * 100)

    widgets_resumo["lbl_reserva"].config(text=f"Reservado: {resumo.reserveMB:.2f} MB")
    widgets_resumo["pb_reserva"].config(value=(resumo.reserveMB / total) * 100)

    widgets_resumo["lbl_livre"].config(text=f"Livre: {resumo.freeMB:.2f} MB")
    widgets_resumo["pb_livre"].config(value=(resumo.freeMB / total) * 100)

    widgets_resumo["lbl_total"].config(text=f"Total: {total:.2f} MB")

# função roda a cada 1s para manter o monitor memoria atualizado
def atualizar_resumo_continuo():
    # se nenhum processo está selecionado, não tem nada para atualizar, sai da função imediatamente
    if pid_resumo_atual is None:
        return
    # so existe depois que clicar em analisar e criou as barras. Se ainda não tiver, não adianta atualizar
    if not widgets_resumo:
        return
    resumo = dll.listar_resumo(c_uint32(pid_resumo_atual))
    mostrar_resumo_inline(pid_resumo_atual, nome_resumo_atual, resumo) # atualiza a interface grafica
    atualizar_resumo_continuo.job_id = root.after(1000, atualizar_resumo_continuo)

# é chamado quando clica no botão analisar, cancela qualquer atualização antiga e inicia uma nova a cada 1s
def iniciar_atualizacao_resumo():
    parar_job(atualizar_resumo_continuo)
    atualizar_resumo_continuo.job_id = root.after(1000, atualizar_resumo_continuo)

# especifica para o botão parar
def parar_monitoramento():
    global pid_resumo_atual, nome_resumo_atual, widgets_resumo
    parar_job(atualizar_resumo_continuo)
    pid_resumo_atual = None
    nome_resumo_atual = None
    widgets_resumo.clear()

    for w in frame_resumo.winfo_children():
        w.destroy()

    tk.Label(frame_resumo,
             text="Monitoramento parado.",
             fg="red").pack(pady=10)

# ABA 2 ------ Funções da primeira aba "Page Faults" - Paginas individual
def abrir_grafico_individual():
    try:
        item = tabela_pf.selection()[0]
    except:
        messagebox.showwarning("Atenção", "Selecione um processo primeiro!")
        return

    pid = int(tabela_pf.item(item, "values")[0])
    nome = tabela_pf.item(item, "values")[1]

    # verifica se existe uma janela aberta com o mesmo PID
    if pid in janelas_individuais:
        janelas_individuais[pid][0].lift()
        return

    win = tk.Toplevel(root)
    win.title(f"Gráfico Individual – {nome} (PID {pid})")
    win.geometry("600x400")

    fig = Figure(figsize=(5, 3), dpi=100)
    ax = fig.add_subplot(111)

    canvas = FigureCanvasTkAgg(fig, win)
    canvas.draw()
    canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)

    tk.Button(win, text="Fechar",
              command=lambda: fechar_grafico_individual(pid)).pack(pady=5)

    # armazena a janela criada. Assim o programa sabe aonde está a janela, o grafico e atualizar ele depois
    janelas_individuais[pid] = (win, ax, canvas)

    atualizar_pf_individual(pid)

# fechar o janela e parar o timer que atualiza a cada 1s    
def fechar_grafico_individual(pid):
    if pid in janelas_individuais:
        win, _, _ = janelas_individuais[pid]
        win.destroy()
        del janelas_individuais[pid]
     # está encerrando o timer para que não fique rodando
    if hasattr(atualizar_pf_individual, "jobs") and pid in atualizar_pf_individual.jobs:
        root.after_cancel(atualizar_pf_individual.jobs[pid])
        del atualizar_pf_individual.jobs[pid]

def atualizar_pf_individual(pid):
    # se não existir janela, não atualiza
    if pid not in janelas_individuais:
        return

    # aqui está buscando os dados win, ax, canvas para mostrar na janela 
    win, ax, canvas = janelas_individuais[pid]

    # se a janela foi fechada no X, encerra tudo
    if not win.winfo_exists():
        fechar_grafico_individual(pid)
        return

    #Verificar se esse PID está no TOP 5
    is_in_top5 = False
    if tracked_pf is not None:
        for pid_top, _ in tracked_pf:
            if pid_top == pid:
                is_in_top5 = True
                break

    # Se estiver no TOP 5, usar o mesmo history_pf do gráfico principal 
    if is_in_top5:
        ys = history_pf.get(pid, [])
    else:
        # Se não estiver no TOP 5, manter um histórico separado só para o gráfico individual 
        if not hasattr(atualizar_pf_individual, "last_pf"):
            atualizar_pf_individual.last_pf = {}
            atualizar_pf_individual.history_ind = {}

        total = dll.obter_page_faults(c_uint32(pid))
        last = atualizar_pf_individual.last_pf.get(pid, total)
        delta = total - last
        atualizar_pf_individual.last_pf[pid] = total

        hist = atualizar_pf_individual.history_ind.setdefault(pid, [])
        hist.append(delta)
        if len(hist) > MAX_PF_POINTS:
            hist.pop(0)

        ys = hist

    # prepara eixo X com base no tamanho do histórico
    xs = list(range(len(ys)))

    # desenha o gráfico
    ax.clear()
    if ys:
        ax.plot(xs, ys, marker="o", linewidth=2)
    ax.set_title(f"Page Faults (Delta) – PID {pid}")
    ax.set_ylabel("Delta Page Faults")
    ax.set_xticks([])
    ax.set_xlabel("")
    ax.grid(True)

    canvas.draw()

    # está criando um loop separado para atualizar a janela individual
    if not hasattr(atualizar_pf_individual, "jobs"):
        atualizar_pf_individual.jobs = {}

    atualizar_pf_individual.jobs[pid] = root.after(
        1000, lambda: atualizar_pf_individual(pid)
    )

# ABA 2 ------ Função da segunda aba "Page Faults" é a função que sustenta toda a aba de Page Faults
def atualizar_page_faults():
    global tracked_pf, history_pf

    # manter a seleção, bug corrigido
    selecionado_pid = None
    try:
        item_sel = tabela_pf.selection()[0]
        selecionado_pid = tabela_pf.item(item_sel, "values")[0]
    except:
        selecionado_pid = None

     # apaga linhas antigas para não ter duplicação
    tabela_pf.delete(*tabela_pf.get_children())

    result = subprocess.run(["tasklist"], capture_output=True, text=True)
    linhas = result.stdout.splitlines()
    processos = []

    for linha in linhas[3:]:
        if not linha.strip():
            continue
        cols = linha.split()
        if len(cols) < 2 or not cols[1].isdigit():
            continue

        nome = cols[0]
        pid = int(cols[1])

        # busca page faults no C e o C retorna com o total de page faults acumulado desde que o processo foi iniciado
        total = dll.obter_page_faults(c_uint32(pid))
        # faz o calculo para saber quantos page faults deu desde a ultima atualização
        delta = total - ultimos_pfs.get(pid, total)
        ultimos_pfs[pid] = total

        processos.append((pid, nome, total, delta))

    # ordena os processos por total de page faults, do maior para o menor (para a tabela)
    processos.sort(key=lambda x: x[2], reverse=True)

    # está preenchendo a tabela com as informaçoes
    for pid, nome, total, delta in processos:
        tabela_pf.insert("", "end", values=(pid, nome, total, delta))

    # restaurar seleção depois de recarregar
    if selecionado_pid is not None:
        for item in tabela_pf.get_children():
            pid_atual = tabela_pf.item(item, "values")[0]
            if str(pid_atual) == str(selecionado_pid):
                tabela_pf.selection_set(item)
                tabela_pf.see(item)
                break

     # escolhe o TOP 5 com base no maior delta
    if tracked_pf is None:
        top5 = sorted(processos, key=lambda x: x[3], reverse=True)[:5]
        tracked_pf = [(p[0], p[1]) for p in top5]
        for pid, _ in tracked_pf:
            history_pf[pid] = []

    #dicionário {pid: delta} para facilitar a atualização do histórico
    delta_por_pid = {p[0]: p[3] for p in processos}

    # atualiza o historico de cada um dos 5 processos e garante que o historico
    for pid, nome in tracked_pf:
        history_pf.setdefault(pid, [])
        history_pf[pid].append(delta_por_pid.get(pid, 0))
        if len(history_pf[pid]) > MAX_PF_POINTS:
            history_pf[pid].pop(0)

    ax_pf.clear()

    # fazendo o desenho do grafico e atualizando com os valores
    for pid, nome in tracked_pf:
        ys = history_pf.get(pid, [])
        xs = list(range(len(ys)))
        ax_pf.plot(xs, ys, marker="o", label=f"{nome} (PID {pid})")

    ax_pf.set_title("Page Faults (Delta) TOP 5")
    ax_pf.set_ylabel("Delta")
    ax_pf.set_xticks([])
    ax_pf.set_xlabel("")
    ax_pf.grid(True)
    ax_pf.legend(fontsize=8, loc="upper left")

    canvas_pf.draw()

    atualizar_page_faults.job_id = root.after(1000, atualizar_page_faults)

# ABA 3 ------ Função da terceira aba "Swap"
def atualizar_swap_usage():
    # faz uma limpa na tabela antes de inserir novos dados
    tabela_swap.delete(*tabela_swap.get_children())

    result = subprocess.run(["tasklist"], capture_output=True, text=True)
    linhas = result.stdout.splitlines()
    processos = []

    for linha in linhas[3:]:
        if not linha.strip():
            continue
        cols = linha.split()
        if len(cols) < 2 or not cols[1].isdigit():
            continue

        nome = cols[0]
        pid = int(cols[1])
        swap = dll.obter_swap_mb(c_uint32(pid))
        processos.append((pid, nome, swap))

    processos.sort(key=lambda x: x[2], reverse=True)

    for pid, nome, swap in processos:
        tabela_swap.insert("", "end", values=(pid, nome, f"{swap:.1f}"))

    atualizar_swap_usage.job_id = root.after(1500, atualizar_swap_usage)

# ABA 4 ------ Função da quarta aba "Fragmentação"
def analisar_fragmentacao():
    try:
        item = tabela.selection()[0]
    except:
        messagebox.showwarning("Atenção", "Selecione um processo na aba Monitor de Memória!")
        return

    pid = int(tabela.item(item, "values")[0])
    nome = tabela.item(item, "values")[1]

    # cria um buffer para receber dados da DLL
    buffer = (MemBloco * MAX_BLOCOS_FRAG)()
    total = dll.listar_fragmentacao(c_uint32(pid), buffer, MAX_BLOCOS_FRAG)

    if total < 0:
        messagebox.showerror("Erro", "Falha ao ler fragmentação.")
        return

    # faz a remoção de todas as linhas antigas para inserir as novas
    tabela_frag.delete(*tabela_frag.get_children())

    blocos = []
    qtd = min(total, MAX_BLOCOS_FRAG)

    # preenche a tabela de fragmentação visual
    for i in range(qtd):
        b = buffer[i]
        if b.regionSize == 0:
            continue

        if b.state == MEM_COMMIT:
            estado = "COMMIT"
        elif b.state == MEM_RESERVE:
            estado = "RESERVE"
        elif b.state == MEM_FREE:
            estado = "FREE"
        else:
            estado = hex(b.state)

        # insere na tabela da interface
        tabela_frag.insert(
            "",
            "end",
            values=(
                f"0x{b.baseAddress:016X}",
                f"{b.regionSize/(1024*1024):.2f}",
                estado
            )
        )

        blocos.append((b.state, b.regionSize))

    # chama a função que desenha o mapa de cores
    desenhar_mapa_fragmentacao(blocos, nome, pid)


def desenhar_mapa_fragmentacao(blocos, nome, pid):
    # limpa o grafico anterior
    ax_frag.clear()

    # se não tiver blocos mostra a mensagem abaixo
    if not blocos:
        ax_frag.set_title("Nenhum bloco para exibir")
        canvas_frag.draw()
        return

    # lê o valor digitado pelo usuário no spinbox
    try:
        max_cells = int(spin_blocos_frag.get())
        if max_cells <= 0:
            max_cells = 1
        if max_cells > MAX_BLOCOS_FRAG:
            max_cells = MAX_BLOCOS_FRAG
    except Exception:
        max_cells = 200

    # pega os primeiros blocos da lista 
    blocks = blocos[:max_cells]
    n = len(blocks)

    # calcula o tamanho da grade
    cols = 20
    rows = (n + cols - 1) // cols
 
    matriz = []  # constroi a matriz de valores
    idx = 0 # indice começa em zero

    # percorre todas as linhas do mapa
    for r in range(rows):
        linha = []
        for c in range(cols):
            if idx < n: # verifica se ainda tem blocos para preencher
                state, _ = blocks[idx] # se tiver blocos, pega o estado dele e converte para o numero da cor
                if state == MEM_COMMIT:
                    v = 2
                elif state == MEM_RESERVE:
                    v = 1
                elif state == MEM_FREE:
                    v = 0
                else:
                    v = -1
                linha.append(v)
            else:
                linha.append(-1)
            idx += 1
        matriz.append(linha)

    cmap = ListedColormap([
        "#000000",  # -1 vazio (sem bloco)
        "#FFFF00",  # 0 FREE
        "#FFA500",  # 1 RESERVE
        "#00FF00",  # 2 COMMIT
    ])

     # ajusta o grafico
    ax_frag.imshow(matriz, aspect="auto", cmap=cmap, vmin=-1, vmax=2)
    ax_frag.set_title(
        f"Mapa de Fragmentação (primeiros {n} blocos)\nPID {pid}"
    )
    ax_frag.set_xticks([])
    ax_frag.set_yticks([])
    canvas_frag.draw() # redesenha tudo na tela

# Limpa a tabela de blocos
def limpar_fragmentacao():
    tabela_frag.delete(*tabela_frag.get_children())

    # Limpa o gráfico
    ax_frag.clear()
    ax_frag.set_title("Mapa de Fragmentação – Limpo")
    ax_frag.set_xticks([])
    ax_frag.set_yticks([])

    # Atualiza a área visual
    canvas_frag.draw()



#  LOOP / ABAS
# parar atualizações continuas
def parar_job(func):
    if hasattr(func, "job_id") and func.job_id:
        try:
            root.after_cancel(func.job_id)
        except:
            pass
        func.job_id = None

# para qualquer atualização contínua das outras abas
def ao_mudar_aba(event=None):
    parar_job(atualizar_page_faults)
    parar_job(atualizar_swap_usage)
    parar_job(atualizar_resumo_continuo)

    aba = abas.tab(abas.select(), "text")

    # se entrar na aba de Page Faults, começa atualizar_page_faults
    if "Page Faults" in aba:
        atualizar_page_faults.job_id = root.after(10, atualizar_page_faults)
    # se entrar na aba de Swap, começa atualizar_swap_usage
    elif "Swap" in aba:
        atualizar_swap_usage.job_id = root.after(10, atualizar_swap_usage)

#  GUI PRINCIPAL
root = tk.Tk()
root.title("Monitor de Memória Virtual – Windows")
root.geometry("1300x820")

abas = ttk.Notebook(root)
abas.pack(fill="both", expand=True)

# ================== Aba 1: Monitor de Memória ==================
frame_mem = tk.Frame(abas)
abas.add(frame_mem, text="Monitor de Memória")

frame_top = tk.Frame(frame_mem)
frame_top.pack(fill=tk.X, padx=10, pady=10)

tk.Label(frame_top, text="Pesquisar processo:").pack(side=tk.LEFT)
entrada_pesquisa = tk.Entry(frame_top, width=30)
entrada_pesquisa.pack(side=tk.LEFT, padx=5)

tk.Button(frame_top, text="Pesquisar", command=pesquisar).pack(side=tk.LEFT, padx=5)
tk.Button(frame_top, text="Listar Todos", command=lambda: listar_processos()).pack(side=tk.LEFT)
tk.Button(frame_top, text="Analisar", command=analisar_processo).pack(side=tk.LEFT, padx=5)
tk.Button(frame_top, text="Parar", command=parar_monitoramento).pack(side=tk.LEFT, padx=5)

# Frame apenas para a tabela e a rolagem
frame_tabela = tk.Frame(frame_mem)
frame_tabela.pack(fill=tk.BOTH, expand=True, padx=10)

# Tabela
tabela = ttk.Treeview(frame_tabela, columns=("PID", "Nome"), show="headings")
tabela.heading("PID", text="PID")
tabela.heading("Nome", text="Nome")
tabela.column("PID", width=80)
tabela.column("Nome", width=400)
tabela.pack(side="left", fill=tk.BOTH, expand=True)

# Scrollbar ao lado da tabela
scroll = ttk.Scrollbar(frame_tabela, orient="vertical", command=tabela.yview)
scroll.pack(side="right", fill="y")

# Liga a tabela com sua scrollbar
tabela.configure(yscroll=scroll.set)

frame_resumo = tk.Frame(frame_mem, relief="sunken", borderwidth=2)
frame_resumo.pack(fill=tk.X, padx=10, pady=10)

listar_processos()

# ================== Aba 2: Page Faults ==================
frame_pf = tk.Frame(abas)
abas.add(frame_pf, text="Page Faults em Tempo Real")

tk.Button(frame_pf, text="Abrir gráfico individual",
          command=abrir_grafico_individual).pack(pady=5)

tabela_pf = ttk.Treeview(
    frame_pf,
    columns=("PID", "Nome", "Total", "Delta"),
    show="headings"
)
tabela_pf.heading("PID", text="PID")
tabela_pf.heading("Nome", text="Nome")
tabela_pf.heading("Total", text="Page Faults Totais")
tabela_pf.heading("Delta", text="Delta")

tabela_pf.column("PID", width=70)
tabela_pf.column("Nome", width=250)
tabela_pf.column("Total", width=150)
tabela_pf.column("Delta", width=120)
tabela_pf.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

frame_graph_pf = tk.Frame(frame_pf)
frame_graph_pf.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

fig_pf = Figure(figsize=(7, 4), dpi=100)
ax_pf = fig_pf.add_subplot(111)

canvas_pf = FigureCanvasTkAgg(fig_pf, master=frame_graph_pf)
canvas_pf.draw()
canvas_pf.get_tk_widget().pack(fill=tk.BOTH, expand=True)

# ================== Aba 3: SWAP ==================
frame_swap = tk.Frame(abas)
abas.add(frame_swap, text="Swap Usage em Tempo Real")

tabela_swap = ttk.Treeview(
    frame_swap,
    columns=("PID", "Nome", "SwapMB"),
    show="headings"
)
tabela_swap.heading("PID", text="PID")
tabela_swap.heading("Nome", text="Nome")
tabela_swap.heading("SwapMB", text="Swap (MB)")

tabela_swap.column("PID", width=70)
tabela_swap.column("Nome", width=250)
tabela_swap.column("SwapMB", width=120)
tabela_swap.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

# ================== Aba 4: Fragmentação ==================
frame_frag = tk.Frame(abas)
abas.add(frame_frag, text="Fragmentação de Memória")

frame_frag_top = tk.Frame(frame_frag)
frame_frag_top.pack(fill=tk.X, padx=10, pady=5)

tk.Label(
    frame_frag_top,
    text="Selecione o processo na aba 'Monitor de Memória'."
).pack(side=tk.LEFT)

tk.Label(frame_frag_top, text="  Blocos no mapa:").pack(side=tk.LEFT, padx=(10, 3))
spin_blocos_frag = tk.Spinbox(frame_frag_top,
                              from_=10,
                              to=MAX_BLOCOS_FRAG,
                              width=6)
spin_blocos_frag.delete(0, tk.END)
spin_blocos_frag.insert(0, "200")
spin_blocos_frag.pack(side=tk.LEFT)

# Botão para limpar o gráfico e a tabela de fragmentação
tk.Button(
    frame_frag_top,
    text="Limpar Tela",
    command=lambda: limpar_fragmentacao()
).pack(side=tk.RIGHT, padx=10)


tk.Button(
    frame_frag_top,
    text="Analisar Fragmentação",
    command=analisar_fragmentacao
).pack(side=tk.RIGHT, padx=10)

frame_frag_bottom = tk.Frame(frame_frag)
frame_frag_bottom.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

# tabela fragmentação
frame_frag_table = tk.Frame(frame_frag_bottom)
frame_frag_table.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

tabela_frag = ttk.Treeview(
    frame_frag_table,
    columns=("Base", "TamanhoMB", "Estado"),
    show="headings"
)
tabela_frag.heading("Base", text="Endereço Base")
tabela_frag.heading("TamanhoMB", text="Tamanho (MB)")
tabela_frag.heading("Estado", text="Estado")

tabela_frag.column("Base", width=200)
tabela_frag.column("TamanhoMB", width=100, anchor="center")
tabela_frag.column("Estado", width=100, anchor="center")

tabela_frag.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

scroll_frag = ttk.Scrollbar(
    frame_frag_table,
    orient="vertical",
    command=tabela_frag.yview
)
tabela_frag.configure(yscroll=scroll_frag.set)
scroll_frag.pack(side=tk.RIGHT, fill="y")

# gráfico fragmentação
frame_frag_graph = tk.Frame(frame_frag_bottom)
frame_frag_graph.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=10)

fig_frag = Figure(figsize=(5, 4), dpi=100)
ax_frag = fig_frag.add_subplot(111)

# ---- Remove números do gráfico desde o início ----
ax_frag.set_xticks([])
ax_frag.set_yticks([])
ax_frag.set_xticklabels([])
ax_frag.set_yticklabels([])

canvas_frag = FigureCanvasTkAgg(fig_frag, master=frame_frag_graph)
canvas_frag.get_tk_widget().pack(fill=tk.BOTH, expand=True)
canvas_frag.draw()

lbl_legenda = tk.Label(
    frame_frag_graph,
    text=(
        "Legenda das cores:\n"
        "Verde  = MEM_COMMIT (memória realmente usada)\n"
        "Laranja = MEM_RESERVE (reservada, mas não usada ainda)\n"
        "Amarelo = MEM_FREE (livre no processo)\n"
        "Preto = Posições Vazias (sem blocos de memória)"
    ),
    justify="left",
    font=("Segoe UI", 9)
)
lbl_legenda.pack(pady=5, anchor="w")

abas.bind("<<NotebookTabChanged>>", ao_mudar_aba)
ao_mudar_aba()

root.mainloop()
