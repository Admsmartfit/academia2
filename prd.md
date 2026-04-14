# PRD — Sistema de Agendamento Inteligente
**Versão:** 1.0  
**Data:** 14/04/2026  
**Escopo:** Módulo de Agendamento (base extensível para o sistema completo de academia)

---

## 1. Visão Geral

Este PRD define o módulo de agendamento de um sistema de gestão para academias, estúdios e prestadores de serviço (professores, instrutores, esteticistas). O foco desta versão é exclusivamente o agendamento — mas toda a arquitetura de dados e rotas foi projetada para receber, sem refatoração, os demais módulos descritos nos PRDs existentes (créditos, gamificação, CRM, WhatsApp, financeiro, LGPD etc.).

**Princípio central:** atrito zero. O prestador cria horários em segundos; o cliente agenda em um clique.

---

## 2. Atores do Sistema

| Ator | Papel | Acesso |
|---|---|---|
| **Prestador** | Professor, instrutor ou esteticista | Área `/provider` |
| **Cliente** | Aluno, paciente ou usuário | Área `/student` (já existente) |
| **Admin** | Dono da academia / gestor | Área `/admin` (já existente) |

> O modelo `User` já existente suporta os roles `admin`, `instructor` e `student`. Este PRD adiciona o role `provider` como alias de `instructor` com permissões de gestão da própria agenda.

---

## 3. Funcionalidades — Prestador

### 3.1 Configuração da Agenda (Regras de Disponibilidade)

O prestador define **templates de disponibilidade semanal** — não horários individuais. O sistema gera os horários automaticamente.

**O que o prestador configura:**
- Dias da semana em que atende (ex: segunda a sexta)
- Horário de início e fim do expediente (ex: 07:00 às 18:00)
- Duração de cada atendimento/aula (ex: 60 min)
- Número máximo de pessoas simultâneas por horário (ex: 10 alunos)
- Período de vigência (ex: válido até o fim do mês ou indeterminado)

**Resultado:** o sistema cria automaticamente todos os `ScheduleSlot`s correspondentes.

**Exemplo:** Professor define segunda a sexta, 07:00–09:00, aulas de 60 min, 10 vagas → sistema cria 2 slots por dia (07:00 e 08:00), cada um com capacidade 10.

### 3.2 Calendário Mensal da Agenda

O prestador visualiza sua agenda em um **calendário mensal interativo** com as seguintes interações:

| Ação | Interação |
|---|---|
| Ver horários do dia | Clicar uma vez na data |
| Criar horário avulso | Clicar uma vez em célula vazia de hora |
| Apagar horário | Clicar duas vezes em horário existente |
| Ver quem está inscrito | Clicar no horário para expandir |

**Estados visuais dos slots no calendário:**
- **Verde:** horário com vagas disponíveis
- **Amarelo:** horário quase cheio (≥ 80% das vagas ocupadas)
- **Vermelho:** horário lotado
- **Cinza tracejado:** horário criado mas sem inscritos
- **Riscado:** horário cancelado

**Vista disponível:** mês (padrão) e semana (alternativa). Sem vista diária por hora — usa cards empilhados.

### 3.3 Gestão de Slots Individuais

Além dos templates, o prestador pode:
- Criar um horário avulso em qualquer data (clique único em célula vazia)
- Cancelar um horário específico (duplo clique → confirmação)
- Alterar o número de vagas de um slot já criado
- Bloquear um dia inteiro (feriado, viagem etc.)
- Ver lista de inscritos de qualquer slot com status (confirmado, cancelado, no-show)

### 3.4 Políticas da Agenda

Configurações globais do prestador:
- **Antecedência mínima para agendamento** (ex: pelo menos 2h antes)
- **Antecedência mínima para cancelamento** (ex: até 4h antes sem penalidade)
- **Janela máxima de agendamento futuro** (ex: agendar com até 30 dias de antecedência)

---

## 4. Funcionalidades — Cliente

### 4.1 Visualização de Disponibilidade

O cliente acessa uma **tabela/grade de horários** com as seguintes características:

- Filtros por prestador, modalidade e data
- Navegação por datas em barra horizontal (scroll lateral, não botões prev/next)
- Cards visuais por horário (não tabela rígida)
- Indicadores visuais de disponibilidade (verde/amarelo/cinza)
- Horários indisponíveis desabilitados visualmente com motivo (lotado, fora do prazo etc.)

### 4.2 Agendamento Avulso

Fluxo em no máximo 2 cliques:
1. Cliente clica em horário disponível
2. Sistema valida e confirma (sem recarregar a página — AJAX)

Se o cliente tiver apenas uma assinatura ativa, ela é selecionada automaticamente. Se tiver mais de uma, exibe seletor.

### 4.3 Agendamento Recorrente

O cliente pode criar um agendamento recorrente a partir de qualquer horário disponível:

- Define frequência: toda semana, a cada 2 semanas
- Define duração: até data específica ou até a assinatura expirar
- Sistema verifica disponibilidade de cada ocorrência futura antes de confirmar
- Para ocorrências sem vaga: informa quais datas estão indisponíveis e pergunta se deseja agendar as disponíveis mesmo assim

**Regras de recorrência:**
- Cada ocorrência futura é validada individualmente (disponibilidade pode variar)
- Cancelar a recorrência cancela apenas as ocorrências futuras (não as passadas)
- Cancelar uma ocorrência individual não cancela as demais

### 4.4 Sugestão de Horários Alternativos

Quando o horário desejado não está disponível (lotado, cancelado ou prestador ausente), o sistema exibe automaticamente:

- Mesmo horário em dias próximos (±3 dias) com o mesmo prestador
- Mesmo horário com prestadores alternativos da mesma modalidade (se aplicável)
- Horários próximos no mesmo dia com o mesmo prestador

As sugestões são ordenadas por menor distância temporal do horário original desejado.

### 4.5 Gestão de Agendamentos do Cliente

Na área do cliente:
- Lista de próximos agendamentos com opção de cancelar
- Histórico de agendamentos passados
- Indicador de agendamentos recorrentes ativos
- Notificação de lembrete (base para integração futura com WhatsApp e push)

---

## 5. Modelos de Dados

### 5.1 Modelos Novos

```python
# Prestador de serviço (extends User)
# Sem novo modelo — usa User com role='instructor'/'provider'
# Campos adicionados ao User existente:
# - bio (Text, nullable)
# - specialties (JSON, nullable)  
# - schedule_policy_json (JSON, nullable)  ← min_notice_hours, max_future_days, cancel_deadline_hours

class ScheduleTemplate(db.Model):
    """Define as regras de disponibilidade semanal do prestador."""
    id               = db.Column(db.Integer, primary_key=True)
    provider_id      = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    modality_id      = db.Column(db.Integer, db.ForeignKey('modality.id'), nullable=True)
    weekdays         = db.Column(db.JSON, nullable=False)     # [0,1,2,3,4] = seg a sex
    start_time       = db.Column(db.Time, nullable=False)
    end_time         = db.Column(db.Time, nullable=False)
    slot_duration_min= db.Column(db.Integer, nullable=False, default=60)
    max_capacity     = db.Column(db.Integer, nullable=False, default=10)
    valid_from       = db.Column(db.Date, nullable=False)
    valid_until      = db.Column(db.Date, nullable=True)      # null = indeterminado
    is_active        = db.Column(db.Boolean, default=True)
    created_at       = db.Column(db.DateTime, default=datetime.utcnow)


class ScheduleSlot(db.Model):
    """Horário concreto gerado a partir de um template ou criado avulsamente."""
    id               = db.Column(db.Integer, primary_key=True)
    provider_id      = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    template_id      = db.Column(db.Integer, db.ForeignKey('schedule_template.id'), nullable=True)
    modality_id      = db.Column(db.Integer, db.ForeignKey('modality.id'), nullable=True)
    date             = db.Column(db.Date, nullable=False)
    start_time       = db.Column(db.Time, nullable=False)
    end_time         = db.Column(db.Time, nullable=False)
    max_capacity     = db.Column(db.Integer, nullable=False)
    status           = db.Column(db.Enum('active','cancelled','full'), default='active')
    cancel_reason    = db.Column(db.String(255), nullable=True)
    created_at       = db.Column(db.DateTime, default=datetime.utcnow)

    # Computed property
    @property
    def booked_count(self):
        return Booking.query.filter_by(slot_id=self.id, status='confirmed').count()

    @property
    def available_spots(self):
        return self.max_capacity - self.booked_count

    @property
    def occupancy_pct(self):
        return (self.booked_count / self.max_capacity * 100) if self.max_capacity else 0


class Booking(db.Model):
    """Reserva de um cliente em um slot. Modelo central."""
    id               = db.Column(db.Integer, primary_key=True)
    client_id        = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    slot_id          = db.Column(db.Integer, db.ForeignKey('schedule_slot.id'), nullable=False)
    subscription_id  = db.Column(db.Integer, db.ForeignKey('subscription.id'), nullable=True)
    recurring_id     = db.Column(db.Integer, db.ForeignKey('recurring_booking.id'), nullable=True)
    status           = db.Column(db.Enum('confirmed','cancelled','completed','no_show'), default='confirmed')
    cost_at_booking  = db.Column(db.Integer, nullable=False, default=0)  # créditos debitados
    booked_at        = db.Column(db.DateTime, default=datetime.utcnow)
    cancelled_at     = db.Column(db.DateTime, nullable=True)
    cancel_reason    = db.Column(db.String(255), nullable=True)
    checked_in_at    = db.Column(db.DateTime, nullable=True)
    xp_awarded       = db.Column(db.Integer, default=0)


class RecurringBooking(db.Model):
    """Série de agendamentos recorrentes."""
    id               = db.Column(db.Integer, primary_key=True)
    client_id        = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    provider_id      = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    modality_id      = db.Column(db.Integer, db.ForeignKey('modality.id'), nullable=True)
    weekday          = db.Column(db.Integer, nullable=False)   # 0=seg … 6=dom
    start_time       = db.Column(db.Time, nullable=False)
    frequency        = db.Column(db.Enum('weekly','biweekly'), default='weekly')
    subscription_id  = db.Column(db.Integer, db.ForeignKey('subscription.id'), nullable=True)
    valid_from       = db.Column(db.Date, nullable=False)
    valid_until      = db.Column(db.Date, nullable=True)
    is_active        = db.Column(db.Boolean, default=True)
    created_at       = db.Column(db.DateTime, default=datetime.utcnow)
```

### 5.2 Modelos Existentes — Campos Adicionados

```python
# Em User (já existe):
bio                  = db.Column(db.Text, nullable=True)
specialties          = db.Column(db.JSON, nullable=True)
schedule_policy_json = db.Column(db.JSON, nullable=True)
# schedule_policy_json exemplo:
# {"min_notice_hours": 2, "cancel_deadline_hours": 4, "max_future_days": 30}

# Em Modality (já existe):
credits_cost         = db.Column(db.Integer, default=1, nullable=False)
slot_duration_min    = db.Column(db.Integer, default=60, nullable=False)
```

### 5.3 Modelos de Base para Módulos Futuros (estrutura preparada, não implementada)

```python
# Para Etapa 2 do PRD_ETAPAS.md:
class Notification(db.Model):
    id, user_id, type, title, message, is_read, created_at

# Para Etapa 3:
class WorkoutLog(db.Model):
    id, user_id, session_exercise_id, sets_done, reps_done, weight_kg, date, notes

# Para Etapa 5:
class Expense(db.Model):
    id, description, category, amount, date, is_recurring, created_by_id

# Para Etapa 6:
class AuditLog(db.Model):
    id, user_id, action, entity_type, entity_id, old_value, new_value, created_at

class ConsentLog(db.Model):
    id, user_id, consent_type, accepted, ip_address, created_at
```

> Criar os arquivos de modelo com `pass` e as colunas comentadas desde o início. Isso evita refatoração de migrations futuras.

---

## 6. Rotas e Blueprints

### 6.1 Blueprint: `provider_bp` — `/provider`

```
GET  /provider/dashboard                  → Resumo do dia (slots de hoje + inscritos)
GET  /provider/calendar                   → Calendário mensal interativo
POST /provider/calendar/slot/create       → Criar slot avulso (AJAX)
POST /provider/calendar/slot/<id>/delete  → Apagar slot (duplo clique, AJAX)
GET  /provider/templates                  → Listar templates de disponibilidade
POST /provider/templates/create           → Criar template + gerar slots
POST /provider/templates/<id>/edit        → Editar template
POST /provider/templates/<id>/delete      → Desativar template
GET  /provider/slot/<id>/attendees        → Lista de inscritos no slot (AJAX)
POST /provider/slot/<id>/cancel           → Cancelar slot (com notificação aos inscritos)
POST /provider/checkin/<booking_id>       → Registrar presença
```

### 6.2 Blueprint: `student_bp` — `/student` (extensão do existente)

```
GET  /student/schedule                    → Grade de horários disponíveis
POST /student/book/<slot_id>              → Agendar avulso (AJAX)
GET  /student/book/<slot_id>/alternatives → Sugestões de horários alternativos (AJAX)
POST /student/recurring/create            → Criar agendamento recorrente
POST /student/booking/<id>/cancel         → Cancelar agendamento
GET  /student/bookings                    → Lista de agendamentos do cliente
GET  /student/bookings/history            → Histórico de aulas realizadas
```

### 6.3 Blueprint: `admin_bp` — `/admin` (extensão do existente)

```
GET  /admin/providers                     → Listar prestadores
POST /admin/providers/create              → Criar prestador (User com role instructor)
GET  /admin/slots                         → Visualizar todos os slots (todos os prestadores)
GET  /admin/bookings                      → Todos os agendamentos (filtros por data, prestador)
```

---

## 7. Lógica de Negócio Crítica

### 7.1 Geração de Slots a partir de Template

```python
def generate_slots_from_template(template: ScheduleTemplate):
    """
    Para cada dia no intervalo [valid_from, valid_until],
    se o weekday estiver na lista do template,
    gera ScheduleSlots de start_time até end_time em intervalos de slot_duration_min.
    Não duplica slots já existentes para o mesmo provider + date + start_time.
    """
```

### 7.2 Validação de Agendamento

```python
def validate_booking(client, slot, subscription=None):
    checks = [
        slot.status == 'active',                          # slot não cancelado
        slot.available_spots > 0,                         # tem vaga
        slot.date >= date.today(),                        # não é passado
        slot.start_time > (datetime.now() + timedelta(hours=policy.min_notice_hours)).time(),
        slot.date <= date.today() + timedelta(days=policy.max_future_days),
        not Booking.query.filter_by(                      # não está já inscrito
            client_id=client.id, slot_id=slot.id,
            status='confirmed').first(),
    ]
    if subscription:
        checks.append(
            subscription.credits_remaining >= (slot.modality.credits_cost if slot.modality else 1)
        )
    return all(checks)
```

### 7.3 Sugestão de Alternativos

```python
def suggest_alternatives(slot: ScheduleSlot, limit=5):
    """
    Busca slots do mesmo provider + mesma start_time em datas ±3 dias
    com available_spots > 0.
    Completa com slots do mesmo provider em horários próximos no mesmo dia.
    Ordena por distância temporal ao slot original.
    """
```

### 7.4 Processamento de Recorrência

```python
def create_recurring_bookings(recurring: RecurringBooking):
    """
    Para cada ocorrência futura dentro do período válido:
    1. Busca o ScheduleSlot correspondente (provider + weekday + start_time + date)
    2. Se disponível → cria Booking e vincula ao RecurringBooking
    3. Se indisponível → registra na lista de conflitos
    Retorna: (criados: list[Booking], conflitos: list[date])
    O cliente é informado dos conflitos antes de confirmar.
    """
```

---

## 8. Interface — Especificações Visuais

### 8.1 Calendário do Prestador

**Tecnologia:** FullCalendar.js (CDN) ou implementação custom em JavaScript puro.

**Comportamento:**
- Click simples em dia → abre painel lateral com slots do dia
- Click simples em célula de horário vazia → modal de criação rápida de slot
- Double click em slot existente → confirmação de exclusão (sem modal complexo)
- Slots coloridos por ocupação: verde (< 50%), amarelo (50–80%), vermelho (> 80%), cinza (sem inscritos)
- Navegação por mês com setas prev/next e botão "Hoje"

**Modal de criação rápida (click em célula vazia):**
```
Data: [pré-preenchida]
Horário início: [pré-preenchido]
Duração: [60 min — editável]
Vagas: [10 — editável]
Modalidade: [select — opcional]
[Cancelar]  [Criar horário]
```

### 8.2 Grade de Horários do Cliente

**Layout:** Cards empilhados (mobile-first), não tabela.

**Card de horário:**
```
[ÍCONE MODALIDADE]  08:00 – 09:00
                    Musculação · Prof. Carlos
                    ████░░░░░░  7/10 vagas

                    [Agendar]   ← botão desabilitado se lotado/bloqueado
```

**Quando lotado, o card exibe:**
```
[ÍCONE]  08:00 – 09:00 · LOTADO
         Ver horários disponíveis ↓
         → 08:00 · 16/04 (3 vagas)
         → 09:00 · hoje (2 vagas)
```

**Filtros disponíveis:**
- Prestador (select)
- Modalidade (select)
- Data (date picker com scroll lateral de dias)

### 8.3 Fluxo de Agendamento Recorrente

```
1. Cliente clica em "Agendar toda semana" em qualquer horário disponível
2. Modal exibe:
   - "Agendar toda [segunda-feira] às [08:00] com [Prof. Carlos]"
   - "Por quanto tempo?" → [Até minha assinatura expirar] ou [Escolher data]
   - "Frequência:" → [Toda semana] [A cada 2 semanas]
3. Sistema calcula ocorrências e mostra prévia:
   - ✓ 21/04 · 28/04 · 05/05 · 12/05 · 19/05  (disponíveis)
   - ✗ 26/05 · sem vaga — sugestão: 27/05 às 08:00
4. Cliente confirma e sistema cria todos os bookings de uma vez
```

---

## 9. Migrações de Banco de Dados

### Ordem de execução

```sql
-- Migration 001: Adicionar campos ao User
ALTER TABLE user ADD COLUMN bio TEXT;
ALTER TABLE user ADD COLUMN specialties JSON;
ALTER TABLE user ADD COLUMN schedule_policy_json JSON;

-- Migration 002: Adicionar campos ao Modality
ALTER TABLE modality ADD COLUMN credits_cost INTEGER NOT NULL DEFAULT 1;
ALTER TABLE modality ADD COLUMN slot_duration_min INTEGER NOT NULL DEFAULT 60;

-- Migration 003: Criar ScheduleTemplate
CREATE TABLE schedule_template (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    provider_id INTEGER NOT NULL REFERENCES user(id),
    modality_id INTEGER REFERENCES modality(id),
    weekdays JSON NOT NULL,
    start_time TIME NOT NULL,
    end_time TIME NOT NULL,
    slot_duration_min INTEGER NOT NULL DEFAULT 60,
    max_capacity INTEGER NOT NULL DEFAULT 10,
    valid_from DATE NOT NULL,
    valid_until DATE,
    is_active BOOLEAN NOT NULL DEFAULT 1,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Migration 004: Criar ScheduleSlot
CREATE TABLE schedule_slot (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    provider_id INTEGER NOT NULL REFERENCES user(id),
    template_id INTEGER REFERENCES schedule_template(id),
    modality_id INTEGER REFERENCES modality(id),
    date DATE NOT NULL,
    start_time TIME NOT NULL,
    end_time TIME NOT NULL,
    max_capacity INTEGER NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'active',
    cancel_reason VARCHAR(255),
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Migration 005: Atualizar Booking (compatível com existente)
ALTER TABLE booking ADD COLUMN slot_id INTEGER REFERENCES schedule_slot(id);
ALTER TABLE booking ADD COLUMN cost_at_booking INTEGER NOT NULL DEFAULT 0;
ALTER TABLE booking ADD COLUMN recurring_id INTEGER REFERENCES recurring_booking(id);
ALTER TABLE booking ADD COLUMN checked_in_at DATETIME;
ALTER TABLE booking ADD COLUMN xp_awarded INTEGER DEFAULT 0;

-- Migration 006: Criar RecurringBooking
CREATE TABLE recurring_booking (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    client_id INTEGER NOT NULL REFERENCES user(id),
    provider_id INTEGER NOT NULL REFERENCES user(id),
    modality_id INTEGER REFERENCES modality(id),
    weekday INTEGER NOT NULL,
    start_time TIME NOT NULL,
    frequency VARCHAR(20) NOT NULL DEFAULT 'weekly',
    subscription_id INTEGER REFERENCES subscription(id),
    valid_from DATE NOT NULL,
    valid_until DATE,
    is_active BOOLEAN NOT NULL DEFAULT 1,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Migrations futuras (estrutura vazia, sem dados):
CREATE TABLE notification (id INTEGER PRIMARY KEY, user_id INTEGER, type VARCHAR(50), title VARCHAR(255), message TEXT, is_read BOOLEAN DEFAULT 0, created_at DATETIME DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE audit_log (id INTEGER PRIMARY KEY, user_id INTEGER, action VARCHAR(100), entity_type VARCHAR(50), entity_id INTEGER, old_value TEXT, new_value TEXT, created_at DATETIME DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE consent_log (id INTEGER PRIMARY KEY, user_id INTEGER, consent_type VARCHAR(50), accepted BOOLEAN, ip_address VARCHAR(45), created_at DATETIME DEFAULT CURRENT_TIMESTAMP);
```

---

## 10. Testes — Casos Críticos

| # | Cenário | Resultado esperado |
|---|---|---|
| 1 | Cliente agenda slot com 1 vaga restante | Booking criado, `available_spots = 0`, slot passa a `full` |
| 2 | Dois clientes tentam a última vaga simultaneamente | Apenas um consegue; o outro recebe sugestão de alternativo |
| 3 | Cliente cria recorrência com 3 datas disponíveis e 1 conflito | 3 bookings criados; conflito listado; cliente decide |
| 4 | Prestador apaga slot com inscritos | Sistema cancela todos os bookings vinculados e notifica clientes |
| 5 | Cliente sem créditos tenta agendar | Erro claro com link para loja de pacotes |
| 6 | Agendamento fora da janela de antecedência mínima | Erro: "Agendamentos devem ser feitos com pelo menos X horas de antecedência" |
| 7 | Cliente cancela booking dentro do prazo | Créditos estornados; slot liberado; `available_spots` incrementa |
| 8 | Template criado com weekdays [0,1,2] e valid_from hoje | Slots gerados corretamente para os próximos 30 dias |
| 9 | Prestador tenta criar slot duplicado (mesma data + horário) | Sistema ignora duplicata silenciosamente |
| 10 | Slot com 0 vagas retorna alternativas | Lista de até 5 sugestões ordenadas por proximidade temporal |

---

## 11. Integração com Módulos Futuros

Esta arquitetura está preparada para receber, sem quebrar o existente:

| Módulo futuro | Ponto de extensão |
|---|---|
| **Créditos variáveis** (PRD Etapa 1) | `cost_at_booking` no `Booking` + `credits_cost` na `Modality` já presentes |
| **Dashboard instrutor** (PRD Etapa 2) | `provider_bp` já inclui rota de checkin e lista de inscritos |
| **Gamificação / XP** | `xp_awarded` no `Booking`; método `checkin()` já mencionado |
| **WhatsApp** (PRD_ETAPAS Etapa 4) | `Booking.cancelled_at` e `Notification` base prontos para triggers |
| **CRM / leads** | Tabela `User` e `AuditLog` prontos; funil conecta na conversão de lead para booking |
| **LGPD** (PRD_ETAPAS Etapa 6) | `ConsentLog` e `AuditLog` criados vazios nesta etapa |
| **NPS / feedback** | Após `Booking.status = completed`, trigger de NPS pode ser disparado |
| **Avaliação física** | `provider_id` no `Booking` permite vincular sessão de avaliação ao slot |

---

## 12. Ordem de Implementação Recomendada

```
Semana 1
  ├── Migrations 001–006
  ├── Modelos Python (ScheduleTemplate, ScheduleSlot, atualizar Booking, RecurringBooking)
  └── Testes unitários dos modelos (validate_booking, suggest_alternatives)

Semana 2
  ├── Blueprint provider_bp (dashboard + templates CRUD)
  ├── Geração de slots a partir de template
  └── Template: provider/dashboard.html e provider/templates.html

Semana 3
  ├── Calendário interativo do prestador (FullCalendar.js ou custom)
  ├── Click simples → criar slot / Double click → apagar
  └── Painel lateral de inscritos por slot

Semana 4
  ├── Grade de horários do cliente (cards mobile-first)
  ├── Agendamento avulso via AJAX
  └── Sugestão de alternativos quando lotado

Semana 5
  ├── Fluxo de agendamento recorrente
  ├── Preview de ocorrências + listagem de conflitos
  └── Cancelamento de recorrência (futura) vs individual

Semana 6
  ├── Testes de todos os casos críticos (seção 10)
  ├── Responsividade mobile
  └── Navbar e botões de voltar em todas as telas profundas
```

---

**Este documento é o PRD de referência para implementação do módulo de agendamento. Os demais PRDs existentes (PRD.md, PRD_ETAPAS.md, PRD_SISTEMA_ACADEMIA.md) seguem sendo válidos para as etapas subsequentes e são compatíveis com esta arquitetura.**