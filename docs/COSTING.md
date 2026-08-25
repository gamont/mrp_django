# Custos industriais — versão 0.4.0

O módulo `apps.costing` implementa custo padrão por versão, roll-up multinível da BOM, custo planejado e real de ordens de produção, preço de compra e análise de variações.

## Sequência operacional
1. Cadastre uma `CostVersion` e as taxas dos centros.
2. Execute o roll-up.
3. Aprove e ative a versão.
4. Calcule o custo planejado da OP na liberação.
5. Após apontamentos e consumos, calcule o custo real.
6. Gere as variações.

## Fórmulas
- PPV = (preço real - custo padrão) × quantidade recebida.
- Variação de consumo = custo real de material - custo planejado de material.
- Variação total = custo real total - custo planejado total.

Valores negativos são favoráveis.
