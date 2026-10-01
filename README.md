# 💣 Minesweeper
Campo minado clássico com visual de terminal retrô, rodando como **executável standalone do Windows**, sem Python, sem dependências, sem instalação. Basta dar dois cliques.
```
M I N E S W E E P E R  [Beginner]
Mines: 10   Flags: 0   Time: 00:07   Best: --:--   Sound: on
Mouse: L=dig R=flag   [Space] Dig  [F] Flag  [C] Chord  [P] Pause  [M] Sound  [N] New  [Q] Quit
    0 1 2 3 4 5 6 7 8
  0 · · 1 1 1 · · · ·
  1 · · 1 ⛑ 1 · 1 1 1
  2 · · 2 2 2 · 1 ⛑ 1
  ...
```
---
## ✨ Recursos
- **🖱️ Suporte a mouse** — clique esquerdo cava, clique direito marca bandeira, direto no tabuleiro (API pura do console Windows via ctypes, zero dependências)
- **⌨️ Teclado completo** — WASD ou setas para mover, atalhos para tudo
- **🔊 Efeitos sonoros** — bipes nativos do Windows (`winsound`): escavação, bandeira, explosão e arpejo de vitória
- **⏱️ Cronômetro ao vivo** — atualiza a cada segundo em segundo plano
- **🏆 Tabela de recordes** — melhor tempo por dificuldade, salvo em `best_times.json` ao lado do executável
- **🛡️ Primeiro clique garantidamente seguro** — as minas só são posicionadas *depois* da primeira escavação, e nunca sob nem ao lado do primeiro clique (a abertura sempre abre uma área em cascata)
- **⏸️ Pausa (P)** — congela o cronômetro e esconde o tabuleiro (anti-trapaça clássico)
- **❓ Interrogações** — F cicla: oculto → bandeira → `?` → oculto
- **✗ Bandeiras erradas** — na derrota, marcações incorretas aparecem com ✗ vermelho
- **🎨 Cores ANSI** — paleta clássica dos números (1–8), minas em vermelho, bandeiras em amarelo, cursor invertido
- **⛏️ Chording (C)** — revela todos os vizinhos quando as bandeiras batem com o número
- **Auto-flag** — as minas são todas marcadas automaticamente na vitória
## 🎮 Como jogar
1. Feche qualquer instância antiga do jogo.
2. Dê dois cliques em **`Minesweeper.exe`** — ⚠️ mantenha-o junto da pasta `_internal` (é o runtime dele).
3. Escolha a dificuldade com **1**, **2** ou **3**.
4. Cave, marque bandeiras, não exploda. 😄
> **Primeira jogada:** ela é sempre segura — o jogo posiciona as minas após o seu primeiro clique, então a abertura sempre revela uma área.
### Controles
| Tecla / Mouse | Ação |
|---|---|
| **Clique esquerdo** | Cavar a célula |
| **Clique direito** | Marcar bandeira |
| **W / A / S / D** ou **setas** | Mover o cursor |
| **Espaço** | Cavar a célula selecionada |
| **F** | Bandeira: oculto → ⛑ → ? → oculto |
| **C** | Chord: revela vizinhos quando as bandeiras batem com o número |
| **P** | Pausar / retomar (esconde o tabuleiro e congela o tempo) |
| **M** | Ligar/desligar o som |
| **N** | Novo jogo com a mesma dificuldade |
| **D** | Mudar de dificuldade (após o fim da partida) |
| **Q** | Sair |
### Dificuldades
| # | Nível | Tabuleiro | Minas |
|---|-------|-----------|-------|
| 1 | Beginner | 9 × 9 | 10 |
| 2 | Intermediate | 16 × 16 | 40 |
| 3 | Expert | 16 × 30 | 99 |
## 🏆 Recordes
Os melhores tempos ficam em `best_times.json`, criado automaticamente na primeira vitória, uma entrada por dificuldade:
```json
{"Beginner": 12, "Intermediate": 88, "Expert": 214}
```
Para zerar os recordes, basta apagar o arquivo.
## 🔨 Compilar a partir do código
Requisito: **Python 3.10+** no Windows (o jogo usa `winsound` e a API de console do Windows).
Opção 1 — script pronto (recomendado):
```bat
build.bat
```
Ele mata instâncias antigas travadas, instala o PyInstaller se faltar, compila e achata a saída para a raiz do projeto.
Opção 2 — comando manual:
```bat
python -m PyInstaller --onedir --name Minesweeper ^
    --distpath . --workpath build --specpath build ^
    src\minesweeper.py
```
> **Por que `--onedir` e não `--onefile`?** O onefile se extrai para `%TEMP%` a cada execução; nesse passo, antivírus costumam bloquear exes não assinados e o jogo morre na hora com `Could not create temporary directory!`. O onedir roda direto da própria pasta, sem extração.
>
> **Nunca use `--noconsole`** — o jogo lê teclado e mouse pela janela de console; sem ela, ele não funciona.
## 📁 Estrutura do projeto
| Item | Descrição |
|---|---|
| `Minesweeper.exe` | O jogo (~1,7 MB) — mantenha junto de `_internal` |
| `_internal\` | Runtime Python + bibliotecas do executável |
| `src\minesweeper.py` | Código-fonte completo (classes `Game` e `Tile`) |
| `build.bat` | Script de compilação em um clique |
| `best_times.json` | Recordes — criado automaticamente na primeira vitória |
| `RELATORIO.md` | Relatório cronológico das mudanças do projeto |
## 🛠️ Notas técnicas
- **Zero dependências em runtime** — mouse via `ReadConsoleInput`/`CONIN$` (ctypes), som via `winsound`, cores via sequências ANSI.
- **QuickEdit desativado** durante o jogo para o Windows não "comer" os cliques; o modo original do console é restaurado ao sair.
- **Wrapper à prova de falhas** — qualquer erro mantém o console aberto mostrando o traceback, em vez de fechar silenciosamente.
- **Ajuste automático de janela** — o console é redimensionado para 110×50 na abertura, garantindo que o tabuleiro (Expert tem 64 colunas) sempre caiba.
## 🐞 Solução de problemas
| Problema | Solução |
|---|---|
| O exe não abre | Verifique se `_internal` está na mesma pasta; rode o `build.bat` novamente |
| "Access denied" ao apagar/recompilar | Feche todas as instâncias do jogo (o `build.bat` já faz isso) |
| Antivírus reclama do exe | Comum com exes PyInstaller não assinados — adicione uma exceção para a pasta |
| Mouse não funciona | O jogo precisa de uma janela de console real — rode direto o `Minesweeper.exe`, não com entrada redirecionada |
| Setas/WASD não respondem | Clique uma vez na janela do jogo para dar foco a ela |
---
Divirta-se! 💣⚑
