Com base na sua solicitação e na análise do código atual (especialmente `student/schedule.html`), você tem toda a razão. O modelo atual (uma barra de datas de rolagem horizontal com cards empilhados embaixo) funciona bem para o dia a dia, mas cria muito atrito quando o aluno quer planejar a longo prazo ou agendar aulas recorrentes. 

Para elaborar esta melhoria, baseei-me nas **melhores práticas de mercado** (usadas por plataformas como Calendly, Acuity Scheduling, Gympass/Wellhub e Mindbody). A principal mudança de paradigma é adotar um **Layout de Duas Colunas (Two-Pane Layout)** em telas maiores, e um fluxo de "seleção de data → seleção de hora" no mobile, com o conceito de "Carrinho de Agendamentos" para as recorrências.

Abaixo, apresento o **PRD (Product Requirements Document)** detalhado para implementar essa melhoria.

---

# PRD: Refatoração da Interface de Agendamento do Aluno

**Versão:** 1.1 (Melhoria de UX/UI)
**Data:** Abril de 2026
**Módulo:** Área do Aluno (`/student`)

## 1. Visão Geral e Problema Atual
Atualmente, o aluno precisa rolar uma barra horizontal para encontrar uma data e não tem visão macro da disponibilidade (semana/mês). O agendamento recorrente fica "escondido" no card de uma aula específica.
**Objetivo:** Redesenhar a interface `student/schedule.html` para torná-la intuitiva, permitindo visão macro (calendário mensal/semanal) e facilitando seleções em lote (ex: "Toda terça às 09:00").

## 2. Melhores Práticas de Mercado Adotadas
1. **Layout Dividido (Desktop):** Calendário à esquerda, horários disponíveis à direita.
2. **Indicadores de Calor (Heatmaps):** O calendário deve ter bolinhas ou cores nos dias (Verde = muita vaga, Amarelo = poucas, Cinza = sem vaga) para evitar que o usuário clique em dias vazios.
3. **Agendamento em Lote (Recorrência Clara):** Ao invés de um pop-up complexo, após clicar em um horário (ex: Terça, 09:00), a interface lateral deve perguntar imediatamente: *"Deseja agendar apenas hoje ou toda terça-feira?"*
4. **Visão de Agenda (List View):** Um botão para ver "Todos os horários da Semana/Mês" em uma lista contínua, ideal para quem tem horários muito flexíveis.

---

## 3. Requisitos Funcionais (FRs)

**FR01: Componente de Calendário (Mini-Calendar)**
* A tela de agendamento deve exibir um calendário mensal interativo.
* O calendário deve permitir alternar entre visão "Mês" e visão "Semana".
* Deve consultar uma nova rota de API para "pintar" os dias com indicadores de disponibilidade (verde/amarelo/cinza) antes mesmo do usuário clicar.

**FR02: Painel Lateral de Horários**
* Ao clicar em um dia no calendário, o painel direito atualiza via AJAX listando os horários (slots) daquele dia.
* Ao lado da data no painel, deve haver um botão: "Ver disponibilidade da semana inteira".

**FR03: Fluxo de Agendamento Recorrente Simplificado**
* Ao clicar em um horário (ex: 09:00), o card se expande ou abre um painel deslizante oferecendo duas opções claras (Radio buttons grandes):
  * `( ) Somente dia 21/04 (Avulso)`
  * `( ) Toda Terça-feira às 09:00 (Recorrente)`
* Se escolher "Recorrente", o sistema exibe imediatamente as próximas 4 ou 8 datas disponíveis com checkboxes. O usuário pode desmarcar uma data específica se souber que vai viajar, por exemplo.

**FR04: Visão Contínua (Agenda do Mês/Semana)**
* Adicionar um toggle (botão de alternância) no topo: `[Visão Calendário] | [Visão Lista]`.
* A "Visão Lista" ignora o calendário e mostra uma lista contínua de todos os slots disponíveis da semana ou mês selecionado, agrupados por dia.

---

## 4. Requisitos Não Funcionais (UI/UX e Arquitetura)

* **Mobile-First:** Em celulares, o calendário fica no topo (recolhível para visão de 1 semana para poupar espaço vertical) e os horários ficam embaixo. Ao rolar para ver os horários, o calendário fica fixo ou minimiza.
* **Biblioteca sugerida:** Utilizar o `Flatpickr` (modo inline) ou uma instância customizada e minimalista do `FullCalendar.js` (que já está no projeto) para o calendário da esquerda.
* **Performance:** A busca de "indicadores de calor" do mês não deve trazer o payload completo dos slots, apenas um resumo `(data: { total_vagas: X })`.

---

## 5. Impacto Técnico e Mudanças no Código

Para suportar a nova interface, o backend (`app/routes/student.py`) precisará de ajustes mínimos, focados na entrega de dados em lote.

### 5.1. Nova Rota API: Resumo do Mês
Criar uma rota leve para alimentar os pontos (bolinhas coloridas) no calendário.
* **Rota:** `GET /student/api/availability/summary`
* **Parâmetros:** `start_date`, `end_date`, `provider_id`, `modality_id`
* **Retorno (JSON):**
  ```json
  {
    "2026-04-20": {"status": "available", "spots": 15},
    "2026-04-21": {"status": "few", "spots": 2},
    "2026-04-22": {"status": "full", "spots": 0}
  }
  ```

### 5.2. Atualização da Rota: `GET /student/api/slots`
* Modificar a rota existente para aceitar um intervalo de datas (`start_date` e `end_date`), em vez de apenas uma data única. Isso permitirá carregar a "Visão Lista" de uma semana inteira de uma só vez.

### 5.3. Frontend: `student/schedule.html`
* **Remover:** A barra de datas horizontal (`.date-strip`).
* **Adicionar:**
  * Container Flex: Esquerda (Calendário Inline, 350px) / Direita (Lista de Slots, flex-1).
  * Lógica em JS para carregar o resumo do mês ao mudar o calendário, e pintar os dias.
  * Lógica para o novo fluxo "Carrinho de Agendamento" ao invés do atual Modal Bottom (`modal-recurring`).

---

## 6. Wireframe em Texto (Guia de Layout Desktop)

```text
+-----------------------------------------------------------------------------+
| Filtros: [ Todos Professores v ] [ Todas Modalidades v ]     [Mês] [Semana] |
+---------------------------------------+-------------------------------------+
|                                       |                                     |
|           ABRIL 2026  [<] [>]         |  Horários para: Terça, 21 de Abril  |
|                                       |  [Ver semana inteira]               |
|   Dom  Seg  Ter  Qua  Qui  Sex  Sáb   |                                     |
|                             1    2    |  +-------------------------------+  |
|    3    4    5    6    7    8    9    |  | 08:00 - 09:00                 |  |
|   10   11   12   13   14   15   16    |  | Musculação · Prof Carlos      |  |
|   17   18   19   20  [21]  22   23    |  | [ Agendar ]                   |  |
|   24   25   26   27   28   29   30    |  +-------------------------------+  |
|                                       |                                     |
|  Legenda:                             |  +-------------------------------+  |
|  (•) Disponível  (•) Últimas vagas    |  | 09:00 - 10:00                 |  |
|                                       |  | Personal · Prof Carlos        |  |
|                                       |  | [ Agendar ]                   |  |
|                                       |  |   ↓                           |  |
|                                       |  |   O Como você quer agendar?   |  |
|                                       |  |   ( ) Apenas dia 21/04        |  |
|                                       |  |   (x) Toda Terça às 09:00     |  |
|                                       |  |       [x] 28/04  [x] 05/05    |  |
|                                       |  |       [x] 12/05  [ ] 19/05    |  |
|                                       |  |   [ Confirmar Agendamentos ]  |  |
|                                       |  +-------------------------------+  |
+---------------------------------------+-------------------------------------+
```

---

## 7. Critérios de Aceite (Plano de Testes)

1. **Navegação de Datas:** Ao abrir a página, o calendário do mês atual deve ser renderizado e o dia de hoje focado automaticamente.
2. **Otimização de API:** Ao mudar de mês no calendário, apenas 1 chamada à API `availability/summary` deve ser feita.
3. **Bloqueio Visual:** Dias passados ou sem nenhum horário criado pelo prestador devem ser in-clicáveis ou visualmente desabilitados (cinza claro).
4. **Agendamento Recorrente Transparente:** Ao selecionar "Toda Terça", a interface deve mostrar claramente quais datas estão sendo reservadas. Se uma das terças futuras já estiver lotada, o checkbox daquele dia deve aparecer desabilitado e com a tag "Lotado".
5. **Mobile Responsivo:** Em telas < 768px, o calendário deve ocupar o topo. Ao clicar em um dia, a tela deve realizar um scroll suave (smooth scroll) até a lista de horários logo abaixo.