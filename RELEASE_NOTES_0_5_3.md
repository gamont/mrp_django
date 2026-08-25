# MRP Django 0.5.3 — Edição operacional em detalhe

- Ações HTMX diretamente na tela da OP.
- Estados operacionais: pronta, setup, execução e interrupção.
- Apontamento por operação com boas, refugo, horas de mão de obra e máquina.
- Conclusão de operação com liberação automática da próxima etapa.
- Baixa manual de material por reserva.
- Suporte a substitutos aprovados e equivalência na baixa manual.
- Proteção idempotente para retries de baixa manual.
- Registro de resultados de inspeção por característica e amostra.
- Formulários dinâmicos para características numéricas, booleanas e texto.
- Timeline atualizada via partial HTMX.
- Permissões Django aplicadas às novas ações.
- Sem migração de banco de dados.
