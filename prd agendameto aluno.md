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


Com base nos documentos e códigos fornecidos, elaborei um **PRD Técnico e Arquitetural Extenso** focado em implementação em etapas (Fases). Este documento foi formatado para que assistentes de IA (como o mencionado) possam consumir e gerar os *commits* e *pull requests* diretamente.

---

# PRD Técnico: Nova Interface de Agendamento do Aluno (Two-Pane & Heatmap)

**Objetivo:** Substituir a rolagem horizontal de datas por um layout de duas colunas com calendário interativo (heatmap de vagas) e facilitar o agendamento recorrente com um fluxo contínuo.

---

## Etapa 1: Backend - Criação das APIs de Consulta (AJAX)

Para que o frontend seja dinâmico, precisamos transformar a busca de horários (que atualmente ocorre via renderização do Jinja no backend) em rotas de API JSON leves.

### 1.1 Nova Rota: Resumo de Vagas (Heatmap)
Adicionar no arquivo `app/routes/student.py`. Esta API retornará o status de ocupação para colorir o calendário.

```python
# Adicionar em app/routes/student.py

@student_bp.route('/api/availability/summary')
@login_required
def api_availability_summary():
    """Retorna o resumo de vagas do mes para pintar o calendario (Heatmap)"""
    start_date_str = request.args.get('start_date')
    end_date_str = request.args.get('end_date')
    
    if not start_date_str or not end_date_str:
        return jsonify({'error': 'start_date and end_date are required'}), 400
        
    try:
        start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
        end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
    except ValueError:
        return jsonify({'error': 'Invalid date format'}), 400

    # Dicionario para armazenar o resultado { 'YYYY-MM-DD': {'spots': X, 'status': 'available'|'few'|'full'} }
    summary = {}
    current_date = start_date
    
    while current_date <= end_date:
        weekday = current_date.weekday()
        weekday_db = 0 if weekday == 6 else weekday + 1
        
        # Buscar todas as grades ativas para o dia da semana
        schedules = ClassSchedule.query.filter_by(
            weekday=weekday_db,
            is_active=True,
            is_approved=True
        ).all()
        
        total_spots_day = 0
        total_capacity = 0
        
        for sched in schedules:
            current_bookings = Booking.query.filter_by(
                schedule_id=sched.id,
                date=current_date,
                status=BookingStatus.CONFIRMED
            ).count()
            
            spots = sched.capacity - current_bookings
            total_spots_day += max(0, spots)
            total_capacity += sched.capacity
            
        date_str = current_date.strftime('%Y-%m-%d')
        
        if total_capacity == 0:
            status = 'none' # Sem aulas no dia
        elif total_spots_day == 0:
            status = 'full'
        elif total_spots_day <= (total_capacity * 0.2): # Menos de 20% das vagas
            status = 'few'
        else:
            status = 'available'
            
        if status != 'none':
            summary[date_str] = {
                'spots': total_spots_day,
                'status': status
            }
            
        current_date += timedelta(days=1)
        
    return jsonify(summary)
```

### 1.2 Nova Rota: Detalhamento de Slots (Visão Diária ou Semanal)
Esta API substituirá a lógica que estava amarrada à rota `/schedule`.

```python
# Adicionar em app/routes/student.py

@student_bp.route('/api/slots')
@login_required
def api_get_slots():
    """Retorna os horarios detalhados para uma data ou intervalo"""
    start_date_str = request.args.get('start_date')
    end_date_str = request.args.get('end_date') # Opcional para visao em lista
    
    if not start_date_str:
        return jsonify({'error': 'start_date is required'}), 400
        
    try:
        start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
        end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date() if end_date_str else start_date
    except ValueError:
        return jsonify({'error': 'Invalid date format'}), 400

    slots_data = []
    current_date = start_date
    
    # Preparar status de saude do usuario (otimizacao)
    parq_ok = current_user.get_screening_status(ScreeningType.PARQ) == ScreeningStatus.APTO
    ems_ok = current_user.has_valid_screening(ScreeningType.EMS)
    
    while current_date <= end_date:
        weekday = current_date.weekday()
        weekday_db = 0 if weekday == 6 else weekday + 1
        
        schedules = ClassSchedule.query.filter_by(
            weekday=weekday_db,
            is_active=True,
            is_approved=True
        ).order_by(ClassSchedule.start_time).all()
        
        day_slots = []
        for sched in schedules:
            current_bookings = Booking.query.filter_by(
                schedule_id=sched.id,
                date=current_date,
                status=BookingStatus.CONFIRMED
            ).count()
            
            available_spots = sched.capacity - current_bookings
            
            user_booked = Booking.query.filter_by(
                user_id=current_user.id,
                schedule_id=sched.id,
                date=current_date,
                status=BookingStatus.CONFIRMED
            ).first() is not None
            
            # Checagem de genero
            gender_restricted = False
            gender_message = ""
            if sched.modality.requires_gender_segregation:
                can_book, msg = GenderDistributionService.can_user_book_slot(current_user, sched.id, current_date)
                if not can_book:
                    gender_restricted = True
                    gender_message = msg
            
            requires_ems = "Eletroestimulacao" in sched.modality.name or "FES" in sched.modality.name
            
            day_slots.append({
                'id': sched.id,
                'start_time': sched.start_time.strftime('%H:%M'),
                'end_time': sched.end_time.strftime('%H:%M'),
                'modality_name': sched.modality.name,
                'modality_icon': sched.modality.icon,
                'instructor_name': sched.instructor.name,
                'available_spots': available_spots,
                'user_booked': user_booked,
                'gender_restricted': gender_restricted,
                'gender_message': gender_message,
                'requires_ems': requires_ems,
                'ems_ok': ems_ok,
                'parq_ok': parq_ok,
                'credits_cost': sched.modality.credits_cost
            })
            
        if day_slots:
            slots_data.append({
                'date': current_date.strftime('%Y-%m-%d'),
                'date_formatted': current_date.strftime('%d/%m/%Y'),
                'slots': day_slots
            })
            
        current_date += timedelta(days=1)

    return jsonify({'data': slots_data})
```

---

## Etapa 2: Refatoração da Rota de Renderização Principal

A rota `@student_bp.route('/schedule')` atual deve ser limpa para servir apenas o "esqueleto" da página.

```python
# Substituir a rota '/schedule' existente em app/routes/student.py

@student_bp.route('/schedule')
@login_required
def schedule():
    """Grade de agendamento (Two-Pane Layout)"""
    if not current_user.cpf or not current_user.gender:
        flash('Por favor, complete seu cadastro (CPF e Sexo) antes de agendar aulas.', 'warning')
        return redirect(url_for('student.profile'))

    # Buscar assinaturas para popular o Seletor de Creditos do Frontend
    active_subscriptions = Subscription.query.filter_by(
        user_id=current_user.id,
        status=SubscriptionStatus.ACTIVE
    ).filter(
        Subscription.credits_used < Subscription.credits_total
    ).all()
    
    # Injetamos dependências básicas. Os slots e heatmap virão via AJAX.
    return render_template('student/schedule_v2.html', 
                           active_subscriptions=active_subscriptions)
```

---

## Etapa 3: Estrutura HTML/CSS (Two-Pane Layout)

Criaremos o arquivo `app/templates/student/schedule_v2.html`. O layout antigo utilizava scroll horizontal para datas. O novo utilizará Flexbox/Grid.

### Dependências Adicionais
Inclua o `Flatpickr` no header ou layout base para o calendário interativo.

```html
{% extends "base.html" %}

{% block title %}Grade de Horários{% endblock %}

{% block head %}
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/flatpickr/dist/flatpickr.min.css">
<style>
    /* Customizacao do Calendario e Heatmap */
    .flatpickr-calendar.inline {
        width: 100%;
        box-shadow: none;
        border: 1px solid #dee2e6;
        border-radius: 8px;
    }
    .status-available { background-color: #d1e7dd !important; color: #0f5132 !important; border-radius: 50%; }
    .status-few { background-color: #fff3cd !important; color: #664d03 !important; border-radius: 50%; }
    .status-full { background-color: #e9ecef !important; color: #6c757d !important; text-decoration: line-through; }
    
    /* Layout Responsivo Duas Colunas */
    @media (min-width: 992px) {
        .layout-twopane { display: flex; gap: 20px; align-items: flex-start; }
        .pane-calendar { flex: 0 0 350px; position: sticky; top: 20px; }
        .pane-slots { flex: 1; }
    }
    .cart-recorrencia {
        background: #f8f9fa;
        border-left: 4px solid #0d6efd;
        padding: 15px;
        margin-top: 10px;
        display: none; /* Ativado via JS */
    }
</style>
{% endblock %}

{% block content %}
<div class="container py-4">
    {% if active_subscriptions %}
    <div class="card mb-4">
        </div>
    {% endif %}

    <div class="d-flex justify-content-end mb-3">
        <div class="btn-group" role="group">
            <button type="button" class="btn btn-outline-primary active" id="btn-view-cal"><i class="fas fa-calendar"></i> Calendário</button>
            <button type="button" class="btn btn-outline-primary" id="btn-view-list"><i class="fas fa-list"></i> Visão Semanal</button>
        </div>
    </div>

    <div class="layout-twopane">
        <div class="pane-calendar" id="calendar-container">
            <div class="card">
                <div class="card-body p-0">
                    <input type="text" id="inline-calendar" class="d-none">
                </div>
                <div class="card-footer bg-white text-muted small">
                    <span class="badge bg-success opacity-75">&nbsp;</span> Disponível 
                    <span class="badge bg-warning opacity-75 text-dark ms-2">&nbsp;</span> Poucas vagas
                </div>
            </div>
        </div>

        <div class="pane-slots">
            <div class="card">
                <div class="card-header bg-white d-flex justify-content-between align-items-center">
                    <h5 class="mb-0" id="slots-title">Selecione uma data</h5>
                </div>
                <div class="card-body" id="slots-container">
                    <div class="text-center py-5 text-muted">
                        <div class="spinner-border text-primary" role="status" id="slots-loader"></div>
                    </div>
                </div>
            </div>
        </div>
    </div>
</div>
{% endblock %}
```

---

## Etapa 4: Frontend - JavaScript e Integração AJAX

Esta lógica será embutida no arquivo `schedule_v2.html` (abaixo do bloco HTML). Implementa o Heatmap e o "Carrinho" de recorrência conforme requerido.

```html
{% block scripts %}
<script src="https://cdn.jsdelivr.net/npm/flatpickr"></script>
<script src="https://npmcdn.com/flatpickr/dist/l10n/pt.js"></script>

<script>
document.addEventListener("DOMContentLoaded", function() {
    let heatmapData = {};
    let selectedDateStr = new Date().toISOString().split('T')[0];
    
    // Configuraçao do Calendário (Flatpickr)
    const fp = flatpickr("#inline-calendar", {
        inline: true,
        locale: "pt",
        defaultDate: "today",
        minDate: "today",
        onChange: function(selectedDates, dateStr, instance) {
            selectedDateStr = dateStr;
            fetchSlots(dateStr, dateStr); // Visão Diaria
        },
        onMonthChange: function(selectedDates, dateStr, instance) {
            fetchHeatmap(instance.currentYear, instance.currentMonth);
        },
        onReady: function(selectedDates, dateStr, instance) {
            fetchHeatmap(instance.currentYear, instance.currentMonth);
            fetchSlots(dateStr, dateStr);
        },
        onDayCreate: function(dObj, dStr, fp, dayElem) {
            // Aplicar Heatmap
            const dateStr = dayElem.dateObj.toISOString().split('T')[0];
            if (heatmapData[dateStr]) {
                dayElem.classList.add(`status-${heatmapData[dateStr].status}`);
            }
        }
    });

    // Função para buscar Heatmap do Mês
    function fetchHeatmap(year, month) {
        // month é 0-indexado no flatpickr
        const startDate = new Date(year, month, 1).toISOString().split('T')[0];
        const endDate = new Date(year, month + 1, 0).toISOString().split('T')[0];
        
        fetch(`/student/api/availability/summary?start_date=${startDate}&end_date=${endDate}`)
            .then(res => res.json())
            .then(data => {
                heatmapData = data;
                fp.redraw(); // Redesenha para aplicar as classes
            });
    }

    // Função para buscar Slots
    function fetchSlots(startDate, endDate) {
        const container = document.getElementById('slots-container');
        const title = document.getElementById('slots-title');
        
        if(startDate === endDate) {
            title.innerHTML = `<i class="fas fa-clock"></i> Horários de ${startDate.split('-').reverse().join('/')}`;
        } else {
            title.innerHTML = `<i class="fas fa-calendar-week"></i> Semana Inteira`;
        }
        
        container.innerHTML = `<div class="text-center py-5"><div class="spinner-border text-primary"></div></div>`;

        fetch(`/student/api/slots?start_date=${startDate}&end_date=${endDate}`)
            .then(res => res.json())
            .then(response => {
                renderSlots(response.data);
            });
    }

    // Função para Renderizar Slots no DOM
    function renderSlots(data) {
        const container = document.getElementById('slots-container');
        if(!data || data.length === 0) {
            container.innerHTML = `<div class="text-center py-4"><i class="fas fa-box-open fa-3x text-muted mb-3"></i><p>Nenhuma aula disponível para esta seleção.</p></div>`;
            return;
        }

        let html = '';
        data.forEach(day => {
            html += `<h6 class="mt-4 border-bottom pb-2">${day.date_formatted}</h6>`;
            day.slots.forEach(slot => {
                // Criação do HTML do Slot baseado nas regras de negocio
                html += `
                <div class="card mb-2 shadow-sm slot-card" data-schedule-id="${slot.id}" data-date="${day.date}">
                    <div class="card-body d-flex justify-content-between align-items-center">
                        <div>
                            <strong>${slot.start_time} - ${slot.end_time}</strong><br>
                            <span class="text-muted">${slot.modality_name} · ${slot.instructor_name}</span>
                        </div>
                        <div>
                            ${getSlotActionHtml(slot, day.date)}
                        </div>
                    </div>
                    
                    <div class="cart-recorrencia" id="cart-${slot.id}-${day.date}">
                        <h6>Como você quer agendar?</h6>
                        <form method="POST" action="/student/book/${slot.id}">
                            <input type="hidden" name="date" value="${day.date}">
                            <input type="hidden" name="subscription_id" class="dynamic-sub-id" value="">
                            
                            <div class="form-check mb-2">
                                <input class="form-check-input" type="radio" name="booking_type" id="avulso_${slot.id}" value="avulso" checked>
                                <label class="form-check-label" for="avulso_${slot.id}">Apenas dia ${day.date_formatted} (Avulso)</label>
                            </div>
                            <div class="form-check mb-3">
                                <input class="form-check-input" type="radio" name="booking_type" id="recorrente_${slot.id}" value="recorrente">
                                <label class="form-check-label" for="recorrente_${slot.id}">Toda semana neste horário (Recorrente)</label>
                            </div>
                            
                            <div class="d-flex justify-content-end gap-2">
                                <button type="button" class="btn btn-sm btn-outline-secondary btn-cancel-cart" data-target="cart-${slot.id}-${day.date}">Cancelar</button>
                                <button type="submit" class="btn btn-sm btn-primary">Confirmar Agendamento</button>
                            </div>
                        </form>
                    </div>
                </div>`;
            });
        });
        container.innerHTML = html;
        bindCartEvents();
    }

    // Regras de bloqueio ou permissão do botão (Mantido lógica original)
    function getSlotActionHtml(slot, date) {
        if (slot.user_booked) return `<span class="badge bg-info">Já agendado</span>`;
        if (slot.gender_restricted) return `<span class="badge bg-secondary">Restrito</span>`;
        if (slot.available_spots <= 0) return `<span class="badge bg-danger">Lotado</span>`;
        if (!slot.parq_ok) return `<a href="/health/parq" class="btn btn-sm btn-warning">Requer Avaliação</a>`;
        if (!slot.ems_ok && slot.requires_ems) return `<a href="/health/ems" class="btn btn-sm btn-warning">Requer Anamnese</a>`;
        
        return `<button class="btn btn-sm btn-primary btn-open-cart" data-target="cart-${slot.id}-${date}">+ Agendar</button>`;
    }

    // Eventos do Carrinho
    function bindCartEvents() {
        document.querySelectorAll('.btn-open-cart').forEach(btn => {
            btn.addEventListener('click', function() {
                // Esconde todos os outros primeiro
                document.querySelectorAll('.cart-recorrencia').forEach(c => c.style.display = 'none');
                // Mostra o clicado
                const targetId = this.getAttribute('data-target');
                document.getElementById(targetId).style.display = 'block';
                
                // Pega a assinatura selecionada no topo da tela
                const activeSub = document.querySelector('input[name="subscription_select"]:checked');
                if(activeSub) {
                    document.getElementById(targetId).querySelector('.dynamic-sub-id').value = activeSub.value;
                }
            });
        });
        
        document.querySelectorAll('.btn-cancel-cart').forEach(btn => {
            btn.addEventListener('click', function() {
                const targetId = this.getAttribute('data-target');
                document.getElementById(targetId).style.display = 'none';
            });
        });
    }

    // Eventos de Toggle Visão Calendário vs Visão Lista (FR04)
    document.getElementById('btn-view-list').addEventListener('click', function() {
        this.classList.add('active');
        document.getElementById('btn-view-cal').classList.remove('active');
        document.getElementById('calendar-container').style.display = 'none'; // Esconde cal
        
        // Pega data atual e soma 7 dias
        const start = selectedDateStr;
        let d = new Date(start);
        d.setDate(d.getDate() + 7);
        const end = d.toISOString().split('T')[0];
        
        fetchSlots(start, end);
    });

    document.getElementById('btn-view-cal').addEventListener('click', function() {
        this.classList.add('active');
        document.getElementById('btn-view-list').classList.remove('active');
        document.getElementById('calendar-container').style.display = 'block'; // Mostra cal
        
        fetchSlots(selectedDateStr, selectedDateStr);
    });
});
</script>
{% endblock %}
```

---

## Etapa 5: Processamento do Agendamento Recorrente via Checkout Unificado

A nova interface (Etapa 4) envia um payload com `booking_type = 'avulso' | 'recorrente'`. Precisamos adaptar o backend `book_class` para lidar com essa nova instrução diretamente do slot.

```python
# Modificar a função 'book_class' no arquivo app/routes/student.py

@student_bp.route('/book/<int:schedule_id>', methods=['POST'])
@login_required
def book_class(schedule_id):
    """Agendar uma aula (Lida com fluxo Avulso e Recorrente)"""
    schedule = ClassSchedule.query.get_or_404(schedule_id)
    date_str = request.form.get('date')
    subscription_id = request.form.get('subscription_id')
    booking_type = request.form.get('booking_type', 'avulso') # Novo campo do UI
    
    # ... (Manter código de Validações Básicas (Data, Assinatura, Saúde, Gênero) original) ...
    #

    if booking_type == 'recorrente':
        # Validar saldo mínimo para criar recorrente
        cost = schedule.modality.credits_cost
        if subscription.credits_remaining < cost:
            flash(f'Você precisa de pelo menos {cost} créditos para criar agendamento recorrente.', 'warning')
            return redirect(url_for('student.schedule'))
            
        existing = RecurringBooking.query.filter_by(
            user_id=current_user.id, schedule_id=schedule_id, is_active=True
        ).first()
        
        if existing:
            flash('Você já possui um agendamento recorrente ativo para este horário.', 'warning')
            return redirect(url_for('student.my_recurring'))
            
        # Cria a recorrencia e o primeiro booking (Lógica extraída de /recurring/create)
        recurring = RecurringBooking(
            user_id=current_user.id,
            subscription_id=subscription.id,
            schedule_id=schedule.id,
            frequency=FrequencyType.WEEKLY, # Assumindo semanal do novo fluxo
            start_date=date,
            end_date=subscription.end_date,
            next_occurrence=date,
            is_active=True
        )
        db.session.add(recurring)
        db.session.commit()
        
        recurring.create_next_booking()
        flash(f'Agendamento RECORRENTE criado com sucesso a partir de {date.strftime("%d/%m/%Y")}!', 'success')
        return redirect(url_for('student.my_bookings'))

    else:
        # Fluxo Avulso (Lógica original de criação de Booking)
        booking = Booking(
            user_id=current_user.id,
            subscription_id=subscription.id,
            schedule_id=schedule.id,
            date=date,
            status=BookingStatus.CONFIRMED,
            is_recurring=False,
            cost_at_booking=schedule.modality.credits_cost
        )
        db.session.add(booking)
        subscription.credits_used += schedule.modality.credits_cost
        db.session.commit()
        
        flash(f'Aula agendada com sucesso! {schedule.modality.name} em {date.strftime("%d/%m/%Y")}', 'success')
        return redirect(url_for('student.my_bookings'))
```