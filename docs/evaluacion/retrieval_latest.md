# Evaluación del retrieval · 2026-11-28T00:32:07+00:00

Embeddings: `ollama:nomic-embed-text-v2-moe` · índice `riopaila_chunks_ollama-nomic-embed-text-v2-moe_20261125005351025710` (embebido (exacto)) · 28 consultas etiquetadas · relevancia binaria por documento.

| Modo | recall@10 | nDCG@10 | MRR | hit@10 | ms/consulta |
|---|---|---|---|---|---|
| densa | 0.991 | 0.934 | 0.941 | 1.000 | 633.3 |
| lexica | 0.884 | 0.762 | 0.735 | 0.893 | 1.9 |
| hibrida | 0.973 | 0.854 | 0.827 | 1.000 | 322.6 |

## Detalle por consulta (modo híbrido)

| id | consulta | recall | nDCG | primer documento |
|---|---|---|---|---|
| R01 | ¿En qué año nació la empresa y cómo ha sido su historia? | 0.50 | 0.24 | `/riopaila-castilla-107-anos-de-compromiso-por-colombia/` |
| R02 | ¿Qué tipos de azúcar comercializa la compañía? | 1.00 | 0.29 | `/bagazo-de-la-cana-de-azucar-2/` |
| R03 | ¿Qué es el jarabe invertido y para qué productos se usa? | 1.00 | 1.00 | `/jarabe-invertido/` |
| R04 | ¿Qué es FertiRio y para qué sirve en los cultivos? | 1.00 | 0.50 | `/innovacion-en-el-campo-estas-son-algunas-de-las-tecnologias-que-lideran-el-futuro-del-agro-colombiano/` |
| R05 | ¿Cómo genera energía renovable a partir del bagazo de caña? | 1.00 | 0.95 | `/bagazo-de-la-cana-de-azucar-2/` |
| R06 | ¿En qué consiste el fondo concursable para iniciativas comunitarias? | 1.00 | 0.46 | `/proyectos-comunitarios-de-17-municipios-de-colombia-podran-acceder-a-fondo-concursable/` |
| R07 | ¿Qué programa apoya el mantenimiento de vías terciarias rurales? | 1.00 | 1.00 | `/caminos-rurales-un-programa-que-apoya-el-mantenimiento-de-vias-terciarias/` |
| R08 | ¿Cuáles son los canales de contacto y la dirección de la oficina principal? | 1.00 | 0.50 | `/inversionistas/` |
| R09 | ¿Qué órganos de gobierno tiene la sociedad? | 1.00 | 1.00 | `/organos-de-gobierno/` |
| R10 | ¿Qué establece el código de ética y buen gobierno? | 1.00 | 1.00 | `/codigo-de-etica-y-buen-gobierno/` |
| R11 | ¿Cómo protege la empresa los datos personales de sus grupos de interés? | 1.00 | 1.00 | `/politica-de-tratamiento-de-datos/` |
| R12 | ¿Qué actividades de ganadería desarrolla el grupo? | 1.00 | 1.00 | `/ganaderia/` |
| R13 | ¿La compañía produce aceite de palma? ¿Dónde? | 1.00 | 1.00 | `/palma-3/` |
| R14 | ¿Qué prácticas de agricultura regenerativa aplica? | 1.00 | 1.00 | `/agricultura-regenerativa/` |
| R15 | ¿Qué nivel obtuvo en la evaluación de sostenibilidad agrícola FSA? | 1.00 | 1.00 | `/riopaila-castilla-alcanza-nivel-plata-en-el-farm-sustainability-assessment-fsa-convirtiendose-en-la-primera-empresa-del-sector-agroindustrial-de-la-cana-en-colombia-con-dicha-certificacion/` |
| R16 | ¿La empresa participa en el mercado de bonos de carbono? | 1.00 | 1.00 | `/riopaila-castilla-incursiona-en-el-mercado-de-bonos-de-carbono/` |
| R17 | ¿Qué calificación crediticia recibió de una agencia calificadora? | 1.00 | 1.00 | `/fitch-ratings-elevo-calificacion-del-grupo-agroindustrial-riopaila-castilla-a-a-con-perspectiva-positiva/` |
| R18 | ¿Cuántos litros de etanol se produjeron en el primer semestre de 2024? | 1.00 | 1.00 | `/riopaila-castilla-produjo-cerca-de-17-millones-de-litros-de-etanol-en-el-primer-semestre/` |
| R19 | ¿Qué donaciones de alcohol entregó durante la pandemia de COVID-19? | 1.00 | 1.00 | `/entregamos-20-mil-litros-de-alcohol-a-la-alcaldia-cali/` |
| R20 | ¿En qué va el proyecto de azúcar orgánica de RioCas? | 1.00 | 0.97 | `/avances-proyecto-azucar-organica-riocas/` |
| R21 | ¿Cómo impulsa el desarrollo de sus proveedores locales? | 0.75 | 0.83 | `/empresa-azucarera-lanzo-estrategia-para-desarrollo-de-sus-proveedores-locales/` |
| R22 | ¿Qué significa el enfoque ambiental, social y de gobernanza de la compañía? | 1.00 | 0.63 | `/sostenibilidad/` |
| R23 | ¿A qué pactos e iniciativas internacionales se ha adherido? | 1.00 | 0.92 | `/adhesiones-pactos-y-reconocimientos/` |
| R24 | ¿Qué mitos sobre el consumo de azúcar aclara la empresa? | 1.00 | 1.00 | `/mitos-del-azucar/` |
| R25 | ¿Cómo funciona el sistema de tratamiento de aguas por aireación? | 1.00 | 1.00 | `/sistema-de-aireacion-extendida/` |
| R26 | ¿Qué comunicó la empresa sobre el caso Policane? | 1.00 | 1.00 | `/comunicado-a-la-opinion-publica-de-riopaila-castilla-sobre-caso-policane/` |
| R27 | ¿Qué resultados financieros reportó el grupo para el año 2023? | 1.00 | 0.63 | `/fitch-ratings-elevo-calificacion-del-grupo-agroindustrial-riopaila-castilla-a-a-con-perspectiva-positiva/` |
| R28 | ¿Cómo respeta y promueve los derechos humanos? | 1.00 | 1.00 | `/derechos-humanos/` |
