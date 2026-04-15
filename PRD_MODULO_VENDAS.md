# PRD — Módulo de Vendas & Onboarding
**Versão:** 1.0  
**Data:** 15/04/2026  
**Escopo:** Captação, qualificação, aula demonstrativa gratuita e conversão para matrícula  
**Depende de:** PRD_AGENDAMENTO.md (ScheduleSlot, Booking, Subscription, User)

---

## 1. Visão Geral

Este módulo implementa a **jornada completa de um novo cliente**, desde o primeiro contato até a matrícula. O fluxo começa com um questionário objetivo de perfil (5 perguntas), sugere modalidades compatíveis — **Musculação** e/ou **EZBody (EMS)** —, permite agendar uma **aula demonstrativa gratuita** sem compra de créditos (janela máxima de 20 dias), e ao final conduz o cliente à aquisição de um pacote.

O módulo também se integra à tela `/student/schedule` existente, adicionando uma entrada de "Descubra seu treino ideal" para qualquer cliente sem assinatura ativa.

**Princípio central:** o cliente experimenta antes de pagar. A venda é consequência de uma experiência vivida.

---

## 2. Conceitos do EZBody (Metodologia EMS)

O **EZBody** é uma modalidade de **eletroestimulação muscular (EMS)** — treino de alta intensidade em 20 minutos que recruta fibras musculares de forma isolada e potente através de corrente elétrica controlada.

### Protocolos por nível (base para a jornada de cliente)

| Fase | Nível | Hz | Foco | Observação |
|---|---|---|---|---|
| Semanas 1–3 | **Iniciante / Adaptação** | 5 Hz fixo | Edema linfático, adaptação neuromuscular | Obrigatória para todos os clientes novos |
| A partir semana 4 | **Intermediário** | 10–55 Hz | Emagrecimento — fibra vermelha | Aumentar 5 Hz conforme resultado estético |
| Avançado | **Hipertrofia** | 60+ Hz | Volume — fibra branca | Apenas após baixo % de gordura |


### Regras médicas relevantes para triagem de clientes

**Contraindicações absolutas (impedem agendamento de demo EZBody):**
- Marcapasso ou implantes metálicos ativos
- Gestantes
- Epilepsia
- Feridas abertas ou inflamações na área de estimulação

**Alertas (não bloqueiam, mas restringem protocolo):**
- Linfedema / Lipedema nos membros → impede fibra branca, permite fibra vermelha
- Uso de medicamentos emagrecedores (semaglutida etc.) → alerta nutricional obrigatório

**Alertas nutricionais exibidos antes da demo EZBody:**
- Nunca fazer EMS em jejum ou restrição severa de carboidratos
- Beber 500ml de água ou isotônico antes da sessão
- Palatinose recomendada para quem usa medicamentos emagrecedores

**Intervalo mínimo entre sessões EMS:** 48 horas. A aula demo de EZBody é uma sessão única — 

### Cronograma intercalado EZBody + Musculação (para apresentar ao cliente)

| Dia | Modalidade | Foco |
|---|---|---|
| Segunda | EZBody (EMS) | Fibra vermelha — emagrecimento corpo todo |
| Terça | Musculação | Hipertrofia MMSS |
| Quarta | Descanso ativo | Caminhada leve |
| Quinta | EZBody (EMS) | Fibra branca — volume e combate à flacidez |
| Sexta | Musculação | Hipertrofia MMII |
| Sábado | Cardio | Gasto calórico basal |

---

## 3. Atores e Fluxos

| Ator | Ponto de entrada | Papel |
|---|---|---|
| **Lead / Visitante** | Link de indicação, QR code, landing page | Faz o questionário, agenda demo |
| **Aluno sem assinatura** | `/student/schedule` (banner) | Acessa o quiz a partir da grade |
| **Aluno com assinatura** | `/student/schedule` (normal) | Usa a grade sem onboarding |
| **Admin** | `/admin/leads` | Visualiza funil de conversão, cria leads manualmente |
| **Prestador** | Dashboard existente | Vê demos agendadas na sua agenda |

---

## 4. Etapas de Implementação

---

### Etapa 1 — Questionário de Perfil (Quiz de Objetivos)

**Objetivo:** Identificar o perfil e preferência do novo cliente em 5 perguntas para sugerir a modalidade e o turno ideal.

#### 4.1.1 Perguntas (uma por tela, mobile-first)

**P1 — Qual é o seu principal objetivo?**
- Emagrecer e definir
- Ganhar massa muscular
- Melhorar saúde e disposição
- Reabilitação / aliviar dores
- Manutenção e qualidade de vida

**P2 — Quanto tempo você tem disponível por sessão?**
- Até 30 minutos
- Entre 30 e 60 minutos
- Mais de 60 minutos

**P3 — Com que frequência pretende treinar?**
- 1–2x por semana
- 3–4x por semana
- Todos os dias

**P4 — Já praticou musculação antes?**
- Sim, treino ou já treinei
- Não, é minha primeira vez

**P5 — Quando você prefere treinar?**
- Manhã (06:00–12:00)
- Tarde (12:00–18:00)
- Noite (18:00–22:00)
- Final de semana

#### 4.1.2 Lógica de Recomendação

```python
def suggest_modalities(answers: dict) -> list[str]:
    """
    Retorna lista de modalidades sugeridas com base nas respostas.
    EZBody SEMPRE é sugerido como opção (exceto contraindicações confirmadas no PAR-Q).
    Musculação é sugerida quando:
      - objetivo in ['ganhar_massa', 'manutencao'] OU
      - tempo >= 30min OU
      - frequencia >= 3x/semana
    """
    suggestions = ['ezbody']

    objetivo = answers.get('objetivo', '')
    tempo    = answers.get('tempo', '')
    freq     = answers.get('frequencia', '')

    if objetivo in ['ganhar_massa', 'manutencao']:
        suggestions.append('musculacao')
    if tempo in ['30_60', 'mais_60']:
        if 'musculacao' not in suggestions:
            suggestions.append('musculacao')
    if freq in ['3_4x', 'todos_dias']:
        if 'musculacao' not in suggestions:
            suggestions.append('musculacao')

    return suggestions
```

#### 4.1.3 Turno de Preferência (mapeamento de P5 para filtro de horário)

```python
TURNO_MAP = {
    'manha': {'start': '06:00', 'end': '12:00'},
    'tarde': {'start': '12:00', 'end': '18:00'},
    'noite': {'start': '18:00', 'end': '22:00'},
    'fds':   {'weekdays': [5, 6]}
}
```

#### 4.1.4 Modelo de Dados — Novo

```python
class LeadProfile(db.Model):
    """Armazena respostas do quiz e estado da jornada de onboarding."""
    __tablename__ = 'lead_profiles'

    id                   = db.Column(db.Integer, primary_key=True)
    user_id              = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)

    # Respostas do quiz
    objetivo             = db.Column(db.String(50), nullable=True)
    tempo_disponivel     = db.Column(db.String(20), nullable=True)
    frequencia           = db.Column(db.String(20), nullable=True)
    experiencia          = db.Column(db.String(20), nullable=True)
    turno                = db.Column(db.String(20), nullable=True)

    # Resultado
    modalities_suggested = db.Column(db.JSON, nullable=True)
    demo_booked_at       = db.Column(db.DateTime, nullable=True)
    converted_at         = db.Column(db.DateTime, nullable=True)

    # Triagem EZBody
    parq_passed          = db.Column(db.Boolean, nullable=True)
    parq_answers         = db.Column(db.JSON, nullable=True)

    # Controle de fluxo
    quiz_completed_at    = db.Column(db.DateTime, nullable=True)
    onboarding_step      = db.Column(db.String(30), default='quiz')
    # Valores: 'quiz' | 'suggestion' | 'parq' | 'booking' | 'confirmed' | 'converted'

    created_at           = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at           = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = db.relationship('User', backref='lead_profile', uselist=False)
```

#### 4.1.5 Campos adicionados ao `Booking` existente

```python
# Em Booking (migration):
booking_type = db.Column(db.Enum('regular', 'demo'), default='regular', nullable=False)
demo_notes   = db.Column(db.Text, nullable=True)
```

#### 4.1.6 Rotas — Etapa 1

```
GET  /onboarding/quiz                   → Tela do quiz (5 steps)
POST /onboarding/quiz/submit            → Salva respostas, retorna sugestões
GET  /onboarding/suggestion             → Tela de resultado com modalidades sugeridas
```

---

### Etapa 2 — Triagem de Saúde (PAR-Q Simplificado para EZBody)

**Objetivo:** Garantir segurança antes de agendar demo de EZBody. Musculação não exige triagem nesta etapa.

#### 4.2.1 Perguntas PAR-Q EZBody

Exibidas somente se EZBody for sugerido, antes do agendamento:

| # | Pergunta | Ação se Sim |
|---|---|---|
| 1 | Você possui marcapasso ou implante elétrico ativo? | Bloqueia EZBody |
| 2 | Você está grávida ou pode estar grávida? | Bloqueia EZBody |
| 3 | Você tem epilepsia ou convulsões frequentes? | Bloqueia EZBody |
| 4 | Você tem feridas abertas ou inflamações na pele? | Bloqueia EZBody |
| 5 | Você tem diagnóstico de Linfedema ou Lipedema? | Alerta — restringe protocolo (não bloqueia) |
| 6 | Você usa medicamentos emagrecedores (semaglutida etc.)? | Exibe alerta nutricional obrigatório |

Se qualquer pergunta bloqueante = Sim: EZBody removido das opções e sistema sugere apenas Musculação com explicação amigável.

#### 4.2.2 Rotas — Etapa 2

```
GET  /onboarding/parq                   → Formulário PAR-Q EZBody
POST /onboarding/parq/submit            → Valida, salva; redireciona para booking
```

---

### Etapa 3 — Agendamento da Aula Demonstrativa

**Objetivo:** Permitir agendamento gratuito, sem créditos, dentro de uma janela de 20 dias.

#### 4.3.1 Regras de Negócio

- `cost_at_booking = 0`, `subscription_id = null`, `booking_type = 'demo'`
- Janela máxima: slot deve estar entre hoje e `hoje + 20 dias`
- Limite de 1 demo por modalidade por cliente
- `NO_SHOW` automático se cliente não aparecer e não cancelar após 15 min do início
- Após demo realizada: trigger notifica admin e exibe tela de conversão

#### 4.3.2 Tela de Agendamento da Demo

Reutiliza os componentes visuais de `student/schedule.html` com diferenças:

| Componente | Grade normal | Grade demo |
|---|---|---|
| Header | "Agendar Aula" | "Agendar aula grátis de [Modalidade]" |
| Pill de créditos | Mostra saldo | Badge verde "Grátis, sem custo" |
| Barra de datas | 14 dias | 20 dias |
| Filter bar | Prestador + Modalidade | Turno (manhã/tarde/noite/fds) |
| Botão do slot | "Agendar" | "Reservar minha vaga gratuita" |
| Botão recorrente | Presente | Ausente |
| Slots além de 20 dias | Visíveis | Ocultos |

#### 4.3.3 Sugestão de Horários Alternativos na Demo

Quando não há slots disponíveis no turno/dia preferido, exibir chips organizados:

```
Outras opções para Musculação:
[Manhã · Seg 21/04]  [Tarde · Qua 23/04]  [Noite · Sex 25/04]
[Sábado · 26/04]     [Manhã · Seg 28/04]
```

Clicar em um chip atualiza a grade via AJAX sem reload de página.

```python
def suggest_demo_slots(modality_id: int, turno: str, from_date: date, limit: int = 8) -> list[ScheduleSlot]:
    """
    Estratégia A: mesmo turno, qualquer dia dentro dos 20 dias.
    Estratégia B (fallback): qualquer turno, mais próximo da data preferida.
    Ordena por data ASC.
    """
```

#### 4.3.4 Rotas — Etapa 3

```
GET  /onboarding/book-demo/<modality_slug>        → Grade de horários para demo
POST /onboarding/book-demo/<modality_slug>        → Confirma reserva (AJAX)
GET  /onboarding/book-demo/<slot_id>/alts         → Alternativas por turno (AJAX)
GET  /onboarding/confirmed                        → Confirmação pós-agendamento
```

---

### Etapa 4 — Integração com `/student/schedule`

**Objetivo:** Expor o quiz e o caminho de demo dentro da grade existente sem quebrar o fluxo de alunos matriculados.

#### 4.4.1 Banner para Clientes Sem Assinatura

Na tela `/student/schedule`, quando `active_subs` está vazio, exibir acima da barra de datas:

```
╔══════════════════════════════════════════════╗
║  Ainda não é aluno?                          ║
║  Responda 5 perguntas e ganhe uma aula       ║
║  GRÁTIS de Musculação ou EZBody!             ║
║                                              ║
║  [Quero minha aula gratuita →]               ║
╚══════════════════════════════════════════════╝
```

#### 4.4.2 Botão "Descubra seu treino" no Topbar

Visível para todos os usuários no topbar de `/student/schedule`:

```html
<a href="/onboarding/quiz" class="btn-discover">
  Descubra seu treino
</a>
```

Se o quiz já foi respondido, o botão vira "Ver suas sugestões →" e leva para `/onboarding/suggestion`.

#### 4.4.3 Filtro por Turno na Grade

Adicionar ao `filter-bar` existente um novo select de turno:

```html
<select name="turno" onchange="this.form.submit()">
  <option value="">Turno</option>
  <option value="manha">Manhã (06–12h)</option>
  <option value="tarde">Tarde (12–18h)</option>
  <option value="noite">Noite (18–22h)</option>
  <option value="fds">Final de semana</option>
</select>
```

O backend filtra `start_time` pelo range do turno antes de retornar os slots. Compatível com os filtros existentes de prestador e modalidade.

#### 4.4.4 Quando o Aluno Já Respondeu o Quiz

Se `LeadProfile.quiz_completed_at` não é nulo:
- Banner da grade é substituído por mini-card com modalidades sugeridas
- Mini-card exibe link "Agendar demo" por modalidade (se ainda não agendou)
- Se todas as demos foram realizadas, mini-card exibe "Matricule-se →"

#### 4.4.5 Extensão da Rota Existente

```
GET /student/schedule?turno=manha|tarde|noite|fds  → filtro por turno adicionado
```

---

### Etapa 5 — Pós-Demo: Tela de Conversão

**Objetivo:** Converter o cliente que fez a demo em aluno pagante.

#### 4.5.1 Trigger de Conversão

Quando `Booking.status` → `COMPLETED` e `booking_type == 'demo'`:

1. Atualiza `LeadProfile.demo_booked_at` e `onboarding_step → 'demo_realizada'`
2. Cria `Notification` para admin/vendedor com dados do lead
3. Exibe tela de conversão na próxima visita ao app
4. (Futuro — PRD_ETAPAS Etapa 4): Dispara WhatsApp com oferta personalizada

#### 4.5.2 Tela de Conversão Pós-Demo (`/onboarding/convert`)

```
"Você fez sua aula de [Modalidade] com [Professor]!

Com base no seu perfil, recomendamos:

[Plano EZBody Semanal]
  1x EZBody/semana + 2x Musculação
  Estimativa: X créditos/mês

[Plano Híbrido Completo]
  2x EZBody + 3x Musculação/semana
  Estimativa: Y créditos/mês

[Escolher meu plano]   [Falar com consultor]"
```

Os planos exibidos são calculados com base nas respostas do quiz (turno e frequência).

#### 4.5.3 Rotas — Etapa 5

```
GET  /onboarding/convert                → Tela de conversão pós-demo
POST /onboarding/convert/select         → Redireciona para loja com plano pré-selecionado
```

---

### Etapa 6 — Painel Admin: Funil de Leads

**Objetivo:** Dar visibilidade ao gestor sobre a taxa de conversão de novos clientes.

#### 4.6.1 Etapas do Funil (via `onboarding_step`)

```
QUIZ → SUGESTÃO → PAR-Q → DEMO AGENDADA → DEMO REALIZADA → MATRICULADO
```

#### 4.6.2 Métricas do Painel Admin

- Total de quizzes iniciados vs completados
- Taxa de conversão quiz → demo agendada
- Taxa de conversão demo → matrícula
- Modalidade mais demandada nas demos
- Turno mais popular por modalidade
- Leads travados em cada etapa do funil

#### 4.6.3 Ações Disponíveis para o Admin

- Ver perfil completo de qualquer lead (respostas do quiz, PAR-Q, demos agendadas)
- Criar lead manualmente (nome + telefone → link de quiz personalizado)
- Marcar lead como "Convertido manualmente" (para vendas presenciais)
- Exportar lista de leads por etapa do funil

#### 4.6.4 Rotas — Etapa 6

```
GET  /admin/leads                       → Lista de leads com filtro por etapa
GET  /admin/leads/<id>                  → Perfil completo do lead
POST /admin/leads/create                → Criar lead manual
POST /admin/leads/<id>/convert          → Marcar como convertido
GET  /admin/leads/funnel                → Dashboard com métricas
```

---

## 5. Modelos de Dados — Resumo Completo

### 5.1 Modelo Novo

```python
class LeadProfile(db.Model):
    __tablename__ = 'lead_profiles'
    id                   = db.Column(db.Integer, primary_key=True)
    user_id              = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, unique=True)
    objetivo             = db.Column(db.String(50))
    tempo_disponivel     = db.Column(db.String(20))
    frequencia           = db.Column(db.String(20))
    experiencia          = db.Column(db.String(20))
    turno                = db.Column(db.String(20))
    modalities_suggested = db.Column(db.JSON)
    parq_passed          = db.Column(db.Boolean)
    parq_answers         = db.Column(db.JSON)
    demo_booked_at       = db.Column(db.DateTime)
    converted_at         = db.Column(db.DateTime)
    quiz_completed_at    = db.Column(db.DateTime)
    onboarding_step      = db.Column(db.String(30), default='quiz')
    created_at           = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at           = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
```

### 5.2 Campos Adicionados a Modelos Existentes

```python
# Em Booking:
booking_type = db.Column(db.Enum('regular', 'demo'), default='regular', nullable=False)
demo_notes   = db.Column(db.Text, nullable=True)

# Em User:
lead_source  = db.Column(db.String(50), nullable=True)
# Valores: 'quiz_organic' | 'referral' | 'admin_manual' | 'qr_code' | 'landing_page'
```

### 5.3 Migration SQL

```sql
-- Migration 008: Módulo de Vendas & Onboarding

CREATE TABLE lead_profiles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL UNIQUE REFERENCES users(id),
    objetivo VARCHAR(50),
    tempo_disponivel VARCHAR(20),
    frequencia VARCHAR(20),
    experiencia VARCHAR(20),
    turno VARCHAR(20),
    modalities_suggested JSON,
    parq_passed BOOLEAN,
    parq_answers JSON,
    demo_booked_at DATETIME,
    converted_at DATETIME,
    quiz_completed_at DATETIME,
    onboarding_step VARCHAR(30) NOT NULL DEFAULT 'quiz',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

ALTER TABLE bookings ADD COLUMN booking_type VARCHAR(10) NOT NULL DEFAULT 'regular';
ALTER TABLE bookings ADD COLUMN demo_notes TEXT;
ALTER TABLE users ADD COLUMN lead_source VARCHAR(50);

CREATE INDEX idx_lead_onboarding_step ON lead_profiles(onboarding_step);
CREATE INDEX idx_booking_type ON bookings(booking_type);
```

---

## 6. Rotas e Blueprints — Visão Completa

### Blueprint: `onboarding_bp` — `/onboarding`

```
GET  /onboarding/quiz                            → Quiz de perfil (5 perguntas)
POST /onboarding/quiz/submit                     → Processa respostas, cria LeadProfile
GET  /onboarding/suggestion                      → Resultado: modalidades sugeridas
GET  /onboarding/parq                            → Triagem EZBody
POST /onboarding/parq/submit                     → Valida PAR-Q
GET  /onboarding/book-demo/<modality_slug>       → Grade de horários demo (20 dias)
POST /onboarding/book-demo/<modality_slug>       → Confirma reserva demo (AJAX)
GET  /onboarding/book-demo/<slot_id>/alts        → Alternativas por turno (AJAX)
GET  /onboarding/confirmed                       → Tela de confirmação
GET  /onboarding/convert                         → Conversão pós-demo
POST /onboarding/convert/select                  → Redireciona para loja
```

### Extensão ao `student_bp` existente

```
GET /student/schedule?turno=manha|tarde|noite|fds
```

### Extensão ao `admin_bp` existente ou novo

```
GET  /admin/leads
GET  /admin/leads/<id>
POST /admin/leads/create
POST /admin/leads/<id>/convert
GET  /admin/leads/funnel
```

---

## 7. Lógica de Negócio Crítica

### 7.1 Validação de Booking Demo

```python
def validate_demo_booking(client, slot) -> tuple[bool, str | None]:
    """
    Checagens específicas para booking_type='demo':
    1. slot.date <= hoje + 20 dias
    2. Não existe demo CONFIRMED/COMPLETED do cliente na mesma modalidade
    3. Slot ativo com vagas disponíveis
    Não verifica créditos (cost_at_booking = 0 por definição).
    """
    today = date.today()
    if slot.date > today + timedelta(days=20):
        return False, "Aulas demonstrativas devem ser agendadas nos próximos 20 dias."

    if slot.status != 'active' or slot.available_spots <= 0:
        return False, "Este horário está indisponível."

    existing = Booking.query.join(ScheduleSlot).filter(
        Booking.client_id == client.id,
        Booking.booking_type == 'demo',
        Booking.status.in_(['confirmed', 'completed']),
        ScheduleSlot.modality_id == slot.modality_id,
    ).first()

    if existing:
        return False, "Você já agendou uma aula demonstrativa desta modalidade."

    return True, None
```

### 7.2 Trigger Pós-Demo Realizada

```python
def on_demo_completed(booking: Booking):
    """
    Chamada quando provider faz checkin em booking com booking_type='demo'.
    - Atualiza LeadProfile.demo_booked_at e onboarding_step
    - Cria Notification para admin
    - (Futuro) Dispara WhatsApp com oferta
    """
    lead = LeadProfile.query.filter_by(user_id=booking.client_id).first()
    if lead:
        lead.demo_booked_at = datetime.utcnow()
        lead.onboarding_step = 'demo_realizada'
        db.session.commit()
```

### 7.3 Filtro de Horários por Turno (extensão do serviço de scheduling)

```python
def filter_slots_by_turno(slots: list[ScheduleSlot], turno: str) -> list[ScheduleSlot]:
    """
    Filtra a lista de slots pelo turno desejado.
    'fds' filtra por weekday in [5, 6].
    Outros turnos filtram por start_time.
    """
    ranges = {
        'manha': (time(6, 0),  time(12, 0)),
        'tarde': (time(12, 0), time(18, 0)),
        'noite': (time(18, 0), time(22, 0)),
    }
    if turno == 'fds':
        return [s for s in slots if s.date.weekday() in [5, 6]]
    if turno in ranges:
        start, end = ranges[turno]
        return [s for s in slots if start <= s.start_time < end]
    return slots
```

---

## 8. Interface — Especificações Visuais

### 8.1 Fluxo do Quiz

- Uma pergunta por tela, navegação prev/next
- Barra de progresso no topo (passo 1 de 5)
- Opções como cards grandes com ícone + texto curto
- Seleção com feedback visual imediato (borda laranja + check)
- Botão "Próximo" fica ativo apenas após seleção
- Última tela: animação "calculando..." por 1,5s antes de mostrar resultado

### 8.2 Tela de Resultado

Para cada modalidade sugerida, exibir card com:
- Ícone + nome da modalidade
- 3 benefícios derivados do quiz
- Tempo de sessão
- Badge "Aula grátis disponível"
- Botão "Agendar agora"

### 8.3 Chips de Alternativas por Turno

Quando sem vagas no turno preferido:

```html
<div class="alt-turnos">
  <p class="text-muted small">Sem vagas no turno preferido. Outras opções:</p>
  <div class="chip-group">
    <button class="chip-turno" data-slot-id="42">Manhã · Seg 21/04</button>
    <button class="chip-turno active" data-slot-id="47">Tarde · Qua 23/04</button>
    <button class="chip-turno" data-slot-id="51">Sábado · 26/04</button>
  </div>
</div>
```

Clicar em um chip atualiza a grade via AJAX sem reload.

---

## 9. Integração com Módulos Futuros

| Módulo | Ponto de extensão já preparado |
|---|---|
| **WhatsApp (PRD_ETAPAS Etapa 4)** | `on_demo_completed()` dispara trigger; LeadProfile alimenta listas |
| **CRM (PRD_ETAPAS Etapa 4.3)** | `LeadProfile` é o modelo base do funil de visitantes |
| **PAR-Q completo** | `parq_answers` em LeadProfile armazena respostas; módulo de saúde pode ampliar |
| **Gamificação** | Primeira demo concluída pode conceder XP inicial e badge "Bem-vindo" |
| **NPS** | Trigger pós-demo pode disparar pesquisa NPS com 1 pergunta |
| **Split bancário** | `booking_type='demo'` tem `cost_at_booking=0`, não entra em comissões |
| **LGPD** | `ConsentLog` já preparado; aceite de termos coletado no passo 1 do quiz |

---

## 10. Casos de Teste Críticos

| # | Cenário | Resultado esperado |
|---|---|---|
| 1 | Cliente completa quiz com objetivo "Emagrecer" e tempo "até 30min" | `modalities_suggested = ['ezbody']`, step = 'suggestion' |
| 2 | Cliente completa quiz com objetivo "Ganhar massa" e frequência "3-4x" | `modalities_suggested = ['ezbody', 'musculacao']` |
| 3 | Cliente declara marcapasso na triagem PAR-Q | EZBody bloqueado; apenas Musculação disponível para demo |
| 4 | Cliente tenta agendar demo para daqui a 25 dias | Slot oculto; janela limitada a 20 dias |
| 5 | Cliente tenta agendar 2 demos de EZBody | Segunda tentativa bloqueada com mensagem clara |
| 6 | Turno manhã sem vagas | Chips de alternativas exibidos; grade atualiza via AJAX |
| 7 | Provider faz checkin na demo | `on_demo_completed()` disparado; notificação para admin criada |
| 8 | Cliente sem assinatura acessa `/student/schedule` | Banner de onboarding exibido |
| 9 | Cliente com assinatura acessa `/student/schedule` | Banner ausente; filtro de turno disponível normalmente |
| 10 | Demo com `booking_type='demo'` | `cost_at_booking = 0`; assinatura não alterada |

---

## 11. Ordem de Implementação

```
Semana 1 — Fundação de dados
  ├── Migration 008 (lead_profiles, booking_type, lead_source)
  ├── Modelo LeadProfile (app/models/lead_profile.py)
  └── Atualizar Booking com booking_type + demo_notes

Semana 2 — Quiz e Sugestão
  ├── Blueprint onboarding_bp (app/routes/onboarding.py)
  ├── Templates: quiz.html + suggestion.html
  ├── Lógica suggest_modalities()
  └── Registro em app/__init__.py

Semana 3 — Triagem PAR-Q + Agendamento Demo
  ├── Template parq.html
  ├── validate_demo_booking() em services/scheduling.py
  ├── Template book_demo.html (grade adaptada com filtro de turno)
  ├── suggest_demo_slots() em services/scheduling.py
  └── filter_slots_by_turno() em services/scheduling.py

Semana 4 — Integração com /student/schedule
  ├── Filtro por turno na rota student.schedule
  ├── Banner de onboarding para clientes sem assinatura
  ├── Botão "Descubra seu treino" no topbar
  └── Mini-card de sugestões para quem já completou o quiz

Semana 5 — Pós-Demo e Conversão
  ├── on_demo_completed() integrado ao checkin do provider
  ├── Template convert.html
  └── Notificação interna para admin

Semana 6 — Painel Admin de Leads
  ├── Rotas /admin/leads
  ├── Templates admin/leads/index.html + funnel.html
  └── Testes de todos os cenários críticos (seção 10)
```

---

**Este PRD é complementar ao PRD_AGENDAMENTO.md. Ambos compartilham os modelos ScheduleSlot, Booking e User. Nenhuma refatoração dos modelos existentes é necessária — apenas adições via migration.**
