# Perfis e permissões — MRP 0.2.1

A autorização usa `Group` e `Permission` do Django. A API exige autenticação e verifica permissões de modelo para cada método HTTP. Ações customizadas definem permissões adicionais quando necessário.

## Sincronização

```bash
python manage.py bootstrap_roles
```

O comando é idempotente: pode ser executado a cada implantação.

## Perfis padrão

| Grupo | Responsabilidade principal | Escrita permitida |
|---|---|---|
| MRP Administradores | Administração integral | Todos os módulos, inclusive exclusão |
| MRP Planejadores | MRP, MPS, cadastros técnicos e capacidade | `common`, `masterdata`, `demand`, `planning` |
| MRP Compradores | Fornecedores, OCs e recebimentos | fornecedores e `purchasing` |
| MRP Produção | Ordens e apontamentos de produção | `production` |
| MRP Almoxarifado | Movimentação e recebimento físico | transações de estoque e recebimentos |
| MRP Vendas | Previsões, pedidos e MPS | `demand` |
| MRP Auditores | Consulta e auditoria | somente leitura |

Todos os grupos recebem `view_*` dos aplicativos MRP. Permissões `delete_*` ficam somente com administradores.

## Ações customizadas da API

Alguns endpoints não correspondem diretamente a `create`, `update` ou `delete`. A versão 0.2.1 mapeia as ações para permissões explícitas, por exemplo:

- ATP: `view_item`;
- CTP e what-if: `add_capacityscenario`;
- executar MRP/CRP: permissões de `planningrun` ou `capacityscenario`;
- converter ordem planejada: `change_plannedorder`;
- receber OC: `add_goodsreceipt`;
- liberar OP: `change_workorder`;
- concluir OP: `add_workordercompletion`.

## Atribuição de usuários

Pelo Admin Django, abra o usuário e associe-o a um ou mais grupos. Por shell:

```python
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group

user = get_user_model().objects.get(username="planejador")
user.groups.add(Group.objects.get(name="MRP Planejadores"))
```

## Recomendações

- Use contas individuais; não compartilhe usuários.
- Restrinja superusuários ao mínimo necessário.
- Revise grupos periodicamente.
- Mantenha exclusões de dados transacionais bloqueadas.
- Use o grupo de auditoria para acesso de consulta independente.
