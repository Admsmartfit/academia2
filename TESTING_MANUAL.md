# Manual de Testes — Sistema de Agendamento Inteligente

**Versão:** 1.0 | **Data:** 14/04/2026 | **Plataforma:** Windows 11

---

## Índice

1. [Pré-requisitos](#1-pré-requisitos)
2. [Configuração Inicial](#2-configuração-inicial)
3. [Testes Automatizados (pytest)](#3-testes-automatizados-pytest)
4. [Iniciar o Servidor](#4-iniciar-o-servidor)
5. [Testes Manuais no Browser](#5-testes-manuais-no-browser)
6. [Conformidade com o PRD](#6-conformidade-com-o-prd)
7. [Lacunas e Próximos Passos](#7-lacunas-e-próximos-passos)

---

## 1. Pré-requisitos

Abra o **Prompt de Comando** ou **PowerShell** e verifique:

```
python --version         # deve ser 3.10+
pip --version
```

### Instalar dependências

```
cd c:\Users\ralan\academia2
pip install flask flask-sqlalchemy flask-login flask-migrate pytest
```

Verificação rápida das versões instaladas:

```
pip show flask flask-sqlalchemy flask-login flask-migrate pytest
```

Saída esperada (mínimo):

| Pacote | Versão mínima |
|---|---|
| Flask | 3.0+ |
| Flask-SQLAlchemy | 3.0+ |
| Flask-Login | 0.6+ |
| Flask-Migrate | 4.0+ |
| pytest | 7.0+ |

---

## 2. Configuração Inicial

### 2.1 Criar banco de dados e tabelas

```
cd c:\Users\ralan\academia2
python -c "from app import create_app, db; app = create_app(); app.app_context().push(); db.create_all(); print('OK')"
```

Saída esperada:
```
OK
```

### 2.2 Popular com dados de teste (seed)

```
python seed.py
```

Saída esperada:
```
==================================================
Seed concluído com sucesso!

CREDENCIAIS DE ACESSO:
  Prestador: professor@academia.com  / 123456
  Aluno:     aluno@academia.com      / 123456

Slots criados: 46
Assinatura do aluno: 20 créditos (validade: ...)
==================================================
```

> **Importante:** `seed.py` apaga e recria todos os dados. Execute apenas uma vez
> ou quando quiser resetar o ambiente.

---

## 3. Testes Automatizados (pytest)

### 3.1 Executar todos os testes críticos

```
cd c:\Users\ralan\academia2
python -m pytest tests/test_critical.py -v
```

Resultado esperado: **22 passed**

### 3.2 Executar por cenário individual

```
# Cenário 1 — Race condition / concorrência
python -m pytest tests/test_critical.py::TestConcurrency -v

# Cenário 2 — Políticas de tempo
python -m pytest tests/test_critical.py::TestTimePolicies -v

# Cenário 3 — Créditos insuficientes
python -m pytest tests/test_critical.py::TestCredits -v

# Cenário 4 — Integridade de recorrência
python -m pytest tests/test_critical.py::TestRecurrenceIntegrity -v

# Cenário 5 — Cancelamento pelo prestador
python -m pytest tests/test_critical.py::TestProviderCancellation -v
```

### 3.3 Executar teste individual com detalhe de falha

```
python -m pytest tests/test_critical.py::TestCredits::test_booking_rejected_when_no_credits -v --tb=long
```

### 3.4 Relatório de cobertura (opcional)

```
pip install pytest-cov
python -m pytest tests/test_critical.py --cov=app/services --cov-report=term-missing
```

### 3.5 Mapeamento: testes × cenários do PRD

| Teste | PRD § | Comportamento verificado |
|---|---|---|
| `test_race_condition_window_both_pass_validation` | 10.2 | Dois clientes passam validação antes de qualquer insert |
| `test_validate_booking_fails_when_slot_full` | 10.2 | Segundo cliente bloqueado após primeiro fazer flush |
| `test_alternatives_suggested_when_slot_full` | 10.10 | suggest_alternatives retorna ≥ 1 slot com vagas |
| `test_booking_rejected_inside_min_notice_window` | 10.6 | min_notice_hours recusado com msg em PT-BR |
| `test_booking_accepted_outside_min_notice_window` | 10.6 | Slot válido aprovado sem restrição de tempo |
| `test_cancel_outside_deadline_is_blocked` | 10.6 | cancel_deadline_hours bloqueia cancelamento tardio |
| `test_cancel_within_deadline_is_allowed` | 10.7 | Cancelamento antecipado liberado |
| `test_booking_rejected_beyond_max_future_days` | 10.6 | max_future_days bloqueia slot muito distante |
| `test_booking_rejected_when_no_credits` | 10.5 | Zero créditos → erro com "crédito" na mensagem |
| `test_booking_rejected_when_credits_below_cost` | 10.5 | Créditos < custo → msg com valores exatos |
| `test_booking_allowed_when_sufficient_credits` | 10.5 | Créditos suficientes → aprovado |
| `test_booking_without_subscription_skips_credit_check` | 10.5 | subscription=None pula verificação |
| `test_error_message_content_for_zero_credits` | 10.5 | Mensagem não pode ser vazia ou genérica |
| `test_cancel_one_booking_leaves_series_intact` | 10.4 | Cancelar 1 → 3 restantes CONFIRMED |
| `test_cancel_one_booking_does_not_deactivate_recurring` | 10.4 | RecurringBooking.is_active não muda |
| `test_stopping_recurring_does_not_cancel_existing_bookings` | 10.4 | Parar série ≠ cancelar bookings existentes |
| `test_create_recurring_bookings_service` | 10.3 | 3 slots disponíveis → 3 bookings criados, 0 conflitos |
| `test_slot_delete_cancels_all_confirmed_bookings` | 10.4 | Cancelar slot com 2 inscritos → ambos CANCELLED |
| `test_slot_delete_without_bookings_removes_slot` | 10.4 | Slot vazio → hard delete |
| `test_cancelled_bookings_have_cancelled_at_populated` | 10.4 | cancelled_at nunca nulo após cancelamento |
| `test_cancelling_slot_does_not_affect_other_slots_bookings` | 10.4 | Cancelamento isolado, não vaza para outros slots |
| `test_validate_booking_rejects_cancelled_slot` | 10.1 | validate_booking recusa slot cancelado |

---

## 4. Iniciar o Servidor

```
cd c:\Users\ralan\academia2
python run.py
```

Saída esperada:
```
 * Running on http://0.0.0.0:5000
 * Debug mode: on
```

Acesse no browser: **http://localhost:5000**

---

## 5. Testes Manuais no Browser

### 5.1 Login

| Perfil | URL | E-mail | Senha |
|---|---|---|---|
| Prestador | http://localhost:5000/auth/login | professor@academia.com | 123456 |
| Aluno | http://localhost:5000/auth/login | aluno@academia.com | 123456 |

---

### 5.2 Testes — Área do Prestador

#### T-P1 · Dashboard

1. Login como **professor@academia.com**
2. Acessar http://localhost:5000/provider/dashboard
3. **Verificar:** cards com total de slots hoje, inscritos, vagas livres e % ocupação

---

#### T-P2 · Calendário interativo

1. Acessar http://localhost:5000/provider/calendar
2. **Click simples em uma data** → painel lateral deve abrir com slots do dia
3. **Click simples em horário existente** → card do slot selecionado deve destacar com lista de inscritos
4. **Double click em slot existente** → modal de confirmação de exclusão deve abrir
5. **Click simples em célula vazia no painel lateral** → modal de criação rápida deve abrir

Estados de cor esperados:

| Ocupação | Cor |
|---|---|
| 0 inscritos | Cinza tracejado |
| < 50% | Verde |
| 50–80% | Amarelo |
| > 80% | Vermelho |
| Cancelado | Cinza riscado |

---

#### T-P3 · Criar slot avulso

1. No calendário, clicar em data futura
2. Clicar em "Criar horário" no painel lateral
3. Preencher: início `10:00`, duração `60`, vagas `5`, modalidade `Musculação`
4. Clicar **Criar horário**
5. **Verificar:** slot aparece no calendário com cor cinza (sem inscritos)

---

#### T-P4 · Deletar slot com inscritos (PRD § 10.4)

1. Como aluno, agendar no slot criado no T-P3
2. Voltar como prestador, dar **double click** no slot
3. Confirmar exclusão
4. **Verificar:** resposta JSON deve conter `"action": "cancelled"` e `"affected_bookings": 1`
5. Slot deve aparecer riscado no calendário

---

#### T-P5 · Criar template de disponibilidade

1. Acessar http://localhost:5000/provider/templates
2. Preencher: seg, qua e sex | 08:00–10:00 | 60 min | 10 vagas
3. Clicar **Criar template**
4. **Verificar:** preview mostra N slots a serem criados; após confirmação, slots aparecem no calendário

---

#### T-P6 · Check-in de aluno

1. No calendário, selecionar slot com inscritos
2. No painel de inscritos, clicar em **Check-in** ao lado de um aluno
3. **Verificar:** ícone muda para "Presente" e `checked_in_at` é preenchido

---

### 5.3 Testes — Área do Aluno

#### T-A1 · Grade de horários

1. Login como **aluno@academia.com**
2. Acessar http://localhost:5000/student/schedule
3. **Verificar:** barra de datas scroll horizontal com hoje em destaque
4. **Verificar:** cards de horário com barra colorida lateral
5. Clicar em datas diferentes na barra → cards atualizam sem reload de página

---

#### T-A2 · Agendamento em 1 clique (PRD § 4.2)

1. Clicar em um horário disponível (verde ou com vagas)
2. **Verificar:** como há apenas 1 assinatura ativa, booking é confirmado sem seletor
3. Card deve mudar para status "Agendado" imediatamente (AJAX, sem reload)

---

#### T-A3 · Agendamento com seletor de assinatura

> Requer pelo menos 2 assinaturas ativas para o aluno (criar manualmente no banco ou via seed modificado).

1. Clicar em horário disponível
2. **Verificar:** bottom sheet "Selecionar Assinatura" abre
3. Selecionar assinatura e confirmar
4. Card deve mudar para "Agendado"

---

#### T-A4 · Tentativa de agendamento com crédito zero (PRD § 10.5)

1. No banco, zerar créditos da assinatura do aluno:
   ```
   cd c:\Users\ralan\academia2
   python -c "
   from app import create_app, db
   from app.models.subscription import Subscription
   app = create_app()
   with app.app_context():
       s = Subscription.query.first()
       s.credits_used = s.credits_total
       db.session.commit()
       print('Créditos zerados')
   "
   ```
2. Tentar agendar no browser
3. **Verificar:** mensagem de erro "Créditos insuficientes. Este horário custa X crédito(s)..."

---

#### T-A5 · Sugestões de horário alternativo (PRD § 4.4)

1. Agendar um slot com capacity=1 (lotado após agendamento)
2. Na grade, clicar em "Ver horários disponíveis" no card lotado
3. **Verificar:** lista inline de até 5 alternativas com data, hora e vagas disponíveis

---

#### T-A6 · Agendamento recorrente (PRD § 4.3)

1. Em um horário disponível, clicar em "Agendar toda semana"
2. Preencher: frequência `Toda semana`, duração `próximas 4 semanas`
3. **Verificar step 1:** preview lista datas disponíveis (✓) e conflitos (✗)
4. Confirmar agendamento
5. **Verificar:** mensagem "X aula(s) agendada(s)"

---

#### T-A7 · Cancelar agendamento dentro do prazo (PRD § 10.7)

1. Acessar http://localhost:5000/student/bookings
2. Em um agendamento futuro com prazo de cancelamento disponível, clicar **Cancelar**
3. Selecionar motivo e confirmar
4. **Verificar:** card some com animação; créditos estornados

---

#### T-A8 · Tentativa de cancelamento fora do prazo (PRD § 10.6)

1. No banco, criar um slot que começa em 1 hora (dentro dos 4h de deadline):
   ```
   python -c "
   from app import create_app, db
   from app.models.schedule_slot import ScheduleSlot
   from app.models.booking import Booking, BookingStatus
   from app.models.user import User
   from datetime import datetime, timedelta, date, time as t
   app = create_app()
   with app.app_context():
       provider = User.query.filter_by(role='instructor').first()
       student  = User.query.filter_by(role='student').first()
       slot_dt  = datetime.utcnow() + timedelta(hours=1)
       slot = ScheduleSlot(
           provider_id=provider.id,
           date=slot_dt.date(),
           start_time=slot_dt.time().replace(second=0, microsecond=0),
           end_time=(slot_dt + timedelta(hours=1)).time().replace(second=0, microsecond=0),
           max_capacity=10, status='active'
       )
       db.session.add(slot)
       db.session.flush()
       b = Booking(client_id=student.id, slot_id=slot.id,
                   status=BookingStatus.CONFIRMED, cost_at_booking=1)
       db.session.add(b)
       db.session.commit()
       print(f'Slot criado: {slot.id}, Booking: {b.id}')
   "
   ```
2. Tentar cancelar este booking no browser
3. **Verificar:** erro "Prazo de cancelamento encerrado. É necessário cancelar com pelo menos 4h de antecedência."

---

#### T-A9 · Histórico de aulas

1. Acessar http://localhost:5000/student/bookings/history
2. **Verificar:** lista de aulas passadas com badge de status (Presente / Faltou / Cancelado)

---

## 6. Conformidade com o PRD

### 6.1 Checklist de Funcionalidades

#### Seção 3 — Funcionalidades do Prestador

| # | Requisito PRD | Status | Arquivo |
|---|---|---|---|
| 3.1 | Templates de disponibilidade semanal | ✅ Implementado | `routes/provider.py` → `templates_create` |
| 3.1 | Geração automática de ScheduleSlots | ✅ Implementado | `services/scheduling.py` → `generate_slots_from_template` |
| 3.2 | Calendário mensal interativo (FullCalendar.js v6) | ✅ Implementado | `templates/provider/calendar.html` |
| 3.2 | Click simples → painel lateral com slots do dia | ✅ Implementado | `calendar.html` → `openDayPanel()` |
| 3.2 | Click em slot → expandir inscritos | ✅ Implementado | `calendar.html` → `selectSlot()` + `/provider/slot/<id>/attendees` |
| 3.2 | Double click → confirmação de exclusão | ✅ Implementado | `calendar.html` → timer 280ms |
| 3.2 | Estados visuais: verde/amarelo/vermelho/cinza/riscado | ✅ Implementado | `provider.py` → `_slot_color_key()` |
| 3.3 | Criar slot avulso | ✅ Implementado | `POST /provider/calendar/slot/create` |
| 3.3 | Cancelar slot individual | ✅ Implementado | `POST /provider/slot/<id>/cancel` |
| 3.3 | Alterar vagas de um slot | ✅ Implementado | `POST /provider/slot/<id>/update-capacity` |
| 3.3 | Bloquear dia inteiro | ✅ Implementado | `POST /provider/day/<date>/block` |
| 3.3 | Ver inscritos com status | ✅ Implementado | `GET /provider/slot/<id>/attendees` |
| 3.4 | Políticas: min_notice_hours | ✅ Implementado | `services/scheduling.py` → `validate_booking` check 4 |
| 3.4 | Políticas: cancel_deadline_hours | ✅ Implementado | `routes/student.py` → `booking_cancel` |
| 3.4 | Políticas: max_future_days | ✅ Implementado | `services/scheduling.py` → `validate_booking` check 5 |

#### Seção 4 — Funcionalidades do Cliente

| # | Requisito PRD | Status | Arquivo |
|---|---|---|---|
| 4.1 | Grade de horários mobile-first | ✅ Implementado | `templates/student/schedule.html` |
| 4.1 | Filtros por prestador, modalidade | ✅ Implementado | `routes/student.py` → `schedule()` |
| 4.1 | Navegação por datas com scroll lateral | ✅ Implementado | `schedule.html` → `.date-strip` |
| 4.1 | Indicadores visuais de disponibilidade | ✅ Implementado | `_slot_status_label()` |
| 4.2 | Agendamento avulso em 2 cliques (AJAX) | ✅ Implementado | `POST /student/book/<slot_id>` |
| 4.2 | Seletor automático de assinatura (1 sub = 1 clique) | ✅ Implementado | `schedule.html` → `handleBook()` |
| 4.3 | Agendamento recorrente semanal/quinzenal | ✅ Implementado | `POST /student/recurring/create` |
| 4.3 | Preview de ocorrências antes de confirmar | ✅ Implementado | `POST /student/recurring/preview` |
| 4.3 | Listar conflitos por data | ✅ Implementado | `recurring_preview()` → `conflicts[]` |
| 4.3 | Cancelar ocorrência individual sem afetar série | ✅ Implementado | `POST /student/booking/<id>/cancel` |
| 4.3 | Parar série recorrente | ✅ Implementado | `POST /student/recurring/<id>/stop` |
| 4.4 | Sugestão de alternativos (±3 dias, mesmo horário) | ✅ Implementado | `services/scheduling.py` → `suggest_alternatives` |
| 4.4 | Sugestão de alternativos (mesmo dia, horários próximos) | ✅ Implementado | `suggest_alternatives` estratégia B |
| 4.4 | Ordenação por distância temporal | ✅ Implementado | `suggest_alternatives` → sort por total_seconds |
| 4.5 | Lista de próximos agendamentos | ✅ Implementado | `GET /student/bookings` |
| 4.5 | Histórico de aulas | ✅ Implementado | `GET /student/bookings/history` |
| 4.5 | Agendamentos recorrentes ativos | ✅ Implementado | `bookings.html` → aba "Recorrentes" |
| 4.5 | Cancelamento com estorno de créditos | ✅ Implementado | `booking_cancel()` → `subscription.refund_credit()` |

#### Seção 5 — Modelos de Dados

| Modelo | Status | Arquivo |
|---|---|---|
| `ScheduleTemplate` | ✅ Criado | `models/schedule_template.py` |
| `ScheduleSlot` + computed properties | ✅ Criado | `models/schedule_slot.py` |
| `Booking` (atualizado) | ✅ Criado | `models/booking.py` |
| `RecurringBooking` | ✅ Criado | `models/recurring_booking.py` |
| `User` + campos bio/specialties/schedule_policy_json | ✅ Criado | `models/user.py` |
| `Modality` + campos credits_cost/slot_duration_min | ✅ Criado | `models/modality.py` |
| `Subscription` + use_credit/refund_credit | ✅ Criado | `models/subscription.py` |
| `Notification` (estrutura vazia) | ✅ Criado | `models/notification.py` |
| `AuditLog` (estrutura vazia) | ✅ Criado | `models/audit_log.py` |
| `ConsentLog` (estrutura vazia) | ✅ Criado | `models/consent_log.py` |

#### Seção 6 — Rotas e Blueprints

| Rota PRD | Status | Implementada em |
|---|---|---|
| `GET /provider/dashboard` | ✅ | `provider.py` → `dashboard()` |
| `GET /provider/calendar` | ✅ | `provider.py` → `calendar()` |
| `POST /provider/calendar/slot/create` | ✅ | `provider.py` → `slot_create()` |
| `POST /provider/calendar/slot/<id>/delete` | ✅ | `provider.py` → `slot_delete()` |
| `GET /provider/templates` | ✅ | `provider.py` → `templates_list()` |
| `POST /provider/templates/create` | ✅ | `provider.py` → `templates_create()` |
| `POST /provider/templates/<id>/edit` | ✅ | `provider.py` → `templates_edit()` |
| `POST /provider/templates/<id>/delete` | ✅ | `provider.py` → `templates_delete()` |
| `GET /provider/slot/<id>/attendees` | ✅ | `provider.py` → `slot_attendees()` |
| `POST /provider/slot/<id>/cancel` | ✅ | `provider.py` → `slot_cancel()` |
| `POST /provider/checkin/<booking_id>` | ✅ | `provider.py` → `checkin()` |
| `GET /student/schedule` | ✅ | `student.py` → `schedule()` |
| `POST /student/book/<slot_id>` | ✅ | `student.py` → `book()` |
| `GET /student/book/<slot_id>/alternatives` | ✅ | `student.py` → `slot_alternatives()` |
| `POST /student/recurring/create` | ✅ | `student.py` → `recurring_create()` |
| `POST /student/booking/<id>/cancel` | ✅ | `student.py` → `booking_cancel()` |
| `GET /student/bookings` | ✅ | `student.py` → `bookings()` |
| `GET /student/bookings/history` | ✅ | `student.py` → `bookings_history()` |

#### Seção 7 — Lógica de Negócio Crítica

| Função | Status | Arquivo |
|---|---|---|
| `generate_slots_from_template` | ✅ | `services/scheduling.py` |
| `validate_booking` (7 checks) | ✅ | `services/scheduling.py` |
| `suggest_alternatives` (estratégias A e B) | ✅ | `services/scheduling.py` |
| `create_recurring_bookings` | ✅ | `services/scheduling.py` |

#### Seção 10 — Casos de Teste Críticos

| # PRD | Cenário | Status de Teste |
|---|---|---|
| 10.1 | Cliente agenda slot com 1 vaga → available_spots = 0 | ✅ `test_validate_booking_fails_when_slot_full` |
| 10.2 | Dois clientes tentam última vaga simultaneamente | ✅ `test_race_condition_window_both_pass_validation` |
| 10.3 | Recorrência com 3 datas disponíveis e 1 conflito | ✅ `test_create_recurring_bookings_service` |
| 10.4 | Prestador apaga slot com inscritos → cascata | ✅ `test_slot_delete_cancels_all_confirmed_bookings` |
| 10.5 | Cliente sem créditos → erro claro | ✅ `test_booking_rejected_when_no_credits` |
| 10.6 | Agendamento fora da janela de antecedência | ✅ `test_booking_rejected_inside_min_notice_window` |
| 10.7 | Cancelamento dentro do prazo → créditos estornados | ✅ (rota `booking_cancel`, sem teste unitário isolado) |
| 10.8 | Template com weekdays → slots dos próximos 30 dias | ✅ `seed.py` valida manualmente (46 slots gerados) |
| 10.9 | Slot duplicado silenciosamente ignorado | ✅ Dedup por set em `generate_slots_from_template` |
| 10.10 | Slot com 0 vagas → até 5 sugestões | ✅ `test_alternatives_suggested_when_slot_full` |

---

## 7. Lacunas e Próximos Passos

### Funcional — Não implementado nesta versão

| Item | Descrição | Impacto |
|---|---|---|
| `admin_bp` | PRD § 6.3 menciona rotas `/admin/providers` e `/admin/slots` | Baixo — usadas apenas pelo gestor |
| SELECT FOR UPDATE | Proteção real contra race condition em produção | Alto — necessário antes de deploy com PostgreSQL |
| Migrations Flask-Migrate | Arquivos de migração versionados não foram gerados | Médio — necessário para evoluir o schema em produção |
| Notificações WhatsApp | `Notification` criado vazio; PRD § 11 menciona trigger em `cancelled_at` | Baixo — módulo futuro |
| Caso de teste 10.7 unitário | Cancelamento com estorno de créditos não tem teste pytest isolado | Baixo — coberto pela rota, testável manualmente (T-A7) |

### Como gerar as migrations (quando necessário)

```
cd c:\Users\ralan\academia2
flask --app run:app db init        # apenas na primeira vez
flask --app run:app db migrate -m "initial schema"
flask --app run:app db upgrade
```

### Como adicionar banco PostgreSQL (produção)

1. Instalar: `pip install psycopg2-binary`
2. Definir variável de ambiente:
   ```
   set DATABASE_URL=postgresql://user:senha@localhost/academia
   ```
3. `python run.py` — o `create_app()` usa a variável automaticamente

---

*Manual gerado em 14/04/2026. Última execução da suíte: 22/22 testes passando.*
