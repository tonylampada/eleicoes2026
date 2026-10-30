# Dicionário de eventos dos logs de urna — 2º turno 2026

Gerado por `scripts/gerar_dicionario.py`. Só lista mensagens efetivamente vistas. Dígitos (horários, contagens, títulos de mesário, números de urna) foram trocados por `#`. Apps: VOTA (votação), GAP (gerenciador da aplicação), LOGD (serviço de log), INITJE (inicialização), ATUE/SCUE (raros).

## Mensagens usadas nas métricas

| mensagem (prefixo) | coluna em `eventos_secao` |
|---|---|
| Urna pronta para receber votos | `hr_abertura_log (1ª no dia) / n_urna_pronta` |
| Procedimento de encerramento confirmado | `hr_encerramento_log` |
| Inicio do Encerramento | `hr_inicio_encerramento_log` |
| O voto do eleitor foi computado | `n_votos_log, horários e intervalos` |
| Voto confirmado para [Presidente] | `n_voto_confirmado_presidente` |
| Eleitor foi habilitado | `n_habilitados, tempo_cabine_mediano_s` |
| Tipo de habilitação do eleitor [biométrica] | `n_hab_biometrica` |
| Solicitação de dado pessoal do eleitor para habilitação manual | `n_hab_manual` |
| Ano de nascimento digitado é igual ao do cadastro | `n_hab_ano_nascimento (sem biometria nem habilitação manual)` |
| Aguardando digitação do identificador do eleitor | `início de uma sessão de habilitação` |
| LOGD: `m.startswith("Urna ligada em ")` | `n_urna_ligada` |
| INITJE: `m == "Urna desligada pela chave"` | `n_desligada_chave` |
| VOTA: `m == "Votação suspensa"` | `n_votacao_suspensa` |
| VOTA: `m == "Mesário confirmou o reinício da votação"` | `n_reinicio_votacao` |
| VOTA: `m == M_PRONTA` | `n_urna_pronta` |
| VOTA: `m == "Urna operando na bateria interna"` | `n_bateria_interna` |
| LOGD: `m == "Log interno da urna de contingência validado com sucesso"` | `n_log_contingencia_validado` |
| LOGD: `m == "Identificado arquivo de log corrompido na ME"` | `n_log_me_corrompido` |
| VOTA: `m.startswith("Impressora sem papel") or m.startswith("Impressora atolada")` | `n_impressora_problema` |
| VOTA: `m.startswith("Encerramento só pode ser solicitado após")` | `n_encerramento_antes_hora` |
| VOTA: `m == "Identificador do eleitor digitado inválido"` | `n_identificador_invalido` |
| VOTA: `m == "Eleitor não encontrado para o identificador informado"` | `n_eleitor_nao_encontrado` |
| VOTA: `m == "O eleitor identificado já votou"` | `n_eleitor_ja_votou` |
| VOTA: `m.startswith("Eleitor impedido - ")` | `n_eleitor_impedido` |
| VOTA: `m == "Justificativa recebida"` | `n_justificativa` |
| VOTA: `m == "Eleitor foi suspenso pelo mesário"` | `n_eleitor_suspenso` |
| VOTA: `m.startswith("Habilitação cancelada")` | `n_hab_cancelada` |
| VOTA: `m.startswith("Solicita digital. Tentativa")` | `n_digital_solicitada` |
| VOTA: `m.startswith("Timeout de reconhecimento do dedo")` | `n_digital_timeout` |
| VOTA: `m.startswith("Digital capturada não corresponde")` | `n_digital_nao_corresponde` |
| VOTA: `m == "Ano de nascimento digitado é diferente do cadastro"` | `n_ano_nasc_diferente` |
| VOTA: `m == "Eleitor corrigiu na tela de confirmação de candidato"` | `n_eleitor_corrigiu` |
| VOTA: `m == "Tecla indevida pressionada"` | `n_tecla_indevida` |
| VOTA: `m == "Voto confirmado para [Presidente]"` | `n_voto_confirmado_presidente` |

## Rotina (todos os níveis) — amostra BA: 600 de 35,476 seções

Modelos presentes em ≥ 1.0% das seções da amostra (GAP: só os 40 mais comuns). Total de modelos distintos na amostra: 1,943.

| app | nível | modelo | ocorrências | % seções |
|---|---|---|--:|--:|
| VOTA | INFO | Solicita digital. Tentativa [#] de [#] | 246,733 | 100.0 |
| VOTA | INFO | Capturada a digital. Tentativa [#] de [#] | 243,856 | 100.0 |
| VOTA | INFO | Aguardando digitação do identificador do eleitor | 181,420 | 100.0 |
| VOTA | INFO | Identificador do eleitor digitado pelo mesário | 174,814 | 100.0 |
| VOTA | INFO | Eleitor foi habilitado | 159,838 | 100.0 |
| VOTA | INFO | Voto confirmado para [Presidente] | 159,830 | 100.0 |
| VOTA | INFO | O voto do eleitor foi computado | 159,830 | 100.0 |
| VOTA | INFO | Foto do eleitor apresentada | 152,154 | 100.0 |
| VOTA | INFO | Tipo de habilitação do eleitor [biométrica] | 139,949 | 100.0 |
| VOTA | INFO | Identificador digitado pelo mesário foi: (Título de eleitor) | 135,535 | 100.0 |
| VOTA | INFO | Número de tentativas de reconhecimento do dedo. Tentativa [#] de [#] | 103,906 | 100.0 |
| VOTA | INFO | Tecla indevida pressionada | 44,050 | 100.0 |
| VOTA | INFO | Solicitação de dado pessoal do eleitor para habilitação manual | 12,605 | 100.0 |
| VOTA | INFO | Solicita digital do mesário | 12,424 | 100.0 |
| VOTA | INFO | Dado digitado confere | 12,197 | 100.0 |
| VOTA | INFO | Espaço livre na MV [#.# MB] | 12,091 | 100.0 |
| VOTA | INFO | Espaço utilizado na MI [#.# MB] | 12,090 | 100.0 |
| VOTA | INFO | Quantidade de memória usada [#.# MB] | 12,090 | 100.0 |
| VOTA | INFO | Espaço utilizado na MV [#.# MB] | 12,089 | 100.0 |
| VOTA | INFO | Operador confirmou o registro de mesários | 5,298 | 100.0 |
| VOTA | INFO | Pedido de leitura da biometria do mesário # | 4,676 | 100.0 |
| VOTA | INFO | Mesário # registrado | 4,445 | 100.0 |
| VOTA | INFO | Operador indagado se continua registrando mesários | 4,438 | 100.0 |
| VOTA | INFO | Inspeção da urna iniciada | 4,003 | 100.0 |
| VOTA | INFO | Inspeção da urna confirmada | 4,003 | 100.0 |
| VOTA | INFO | Inspeção da urna terminada | 4,002 | 100.0 |
| VOTA | INFO | Início de impressão | 1,925 | 100.0 |
| VOTA | INFO | Fim de impressão | 1,923 | 100.0 |
| VOTA | INFO | Operador indagado se ocorrerá registro de mesários | 1,356 | 100.0 |
| VOTA | INFO | Operador encerrou ciclo de registro de mesários | 1,352 | 100.0 |
| VOTA | INFO | Urna operando na rede elétrica | 1,097 | 100.0 |
| VOTA | INFO | Operador selecionou: Encerrar votação | 673 | 100.0 |
| VOTA | INFO | Urna pronta para receber votos | 671 | 100.0 |
| VOTA | INFO | Operador indagado se todas as pessoas presentes votaram | 647 | 100.0 |
| VOTA | INFO | Todas as pessoas presentes já votaram? SIM | 637 | 100.0 |
| VOTA | INFO | Imprimindo relatório [BU] via nº [#] | 619 | 100.0 |
| VOTA | INFO | Mesário indagado sobre qualidade do Boletim de Urna | 619 | 100.0 |
| VOTA | INFO | Título digitado para encerramento: # | 607 | 100.0 |
| VOTA | INFO | Aguardando confirmação para emissão da zerésima | 606 | 100.0 |
| VOTA | INFO | Imprimindo relatório [ZERÉSIMA] via nº [#] | 603 | 100.0 |
| VOTA | INFO | Imprimindo relatório [RESUMO DA ZERÉSIMA] via nº [#] | 603 | 100.0 |
| VOTA | INFO | Gerando relatório [ZERÉSIMA] [INÍCIO] | 602 | 100.0 |
| VOTA | INFO | Gerando relatório [ZERÉSIMA] [TÉRMINO] | 601 | 100.0 |
| VOTA | INFO | Gerando relatório [RESUMO DA ZERÉSIMA] [INÍCIO] | 601 | 100.0 |
| VOTA | INFO | Gerando relatório [RESUMO DA ZERÉSIMA] [TÉRMINO] | 601 | 100.0 |
| VOTA | INFO | Procedimento de encerramento confirmado | 600 | 100.0 |
| VOTA | INFO | Inicio do Encerramento | 600 | 100.0 |
| VOTA | INFO | Gerando relatório [BU] [INÍCIO] | 600 | 100.0 |
| VOTA | INFO | Gerando relatório [BU] [TÉRMINO] | 600 | 100.0 |
| VOTA | INFO | Gerando relatório [BUJ] [INÍCIO] | 600 | 100.0 |
| VOTA | INFO | Gerando relatório [BUJ] [TÉRMINO] | 600 | 100.0 |
| VOTA | INFO | Gerando relatório [BIM] [INÍCIO] | 600 | 100.0 |
| VOTA | INFO | Gerando relatório [BIM] [TÉRMINO] | 600 | 100.0 |
| VOTA | INFO | Gerando relatório [ELEITORES HABILITADOS BIOGRAFICAMENTE] [INÍCIO] | 600 | 100.0 |
| VOTA | INFO | Gerando relatório [ELEITORES HABILITADOS BIOGRAFICAMENTE] [TÉRMINO] | 600 | 100.0 |
| VOTA | INFO | Mesário indicou qualidade OK para Boletim de Urna | 600 | 100.0 |
| VOTA | INFO | Gerando arquivo de resultado [bu.dat] + [Início] | 600 | 100.0 |
| VOTA | INFO | Gerando arquivo de resultado [bu.dat] + [Término] | 600 | 100.0 |
| VOTA | INFO | Gerando arquivo de resultado [rdv.dat] + [Início] | 600 | 100.0 |
| VOTA | INFO | Gerando arquivo de resultado [rdv.dat] + [Término] | 600 | 100.0 |
| VOTA | INFO | Gerando arquivo de resultado [jufa.dat] + [Início] | 600 | 100.0 |
| VOTA | INFO | Gerando arquivo de resultado [jufa.dat] + [Término] | 600 | 100.0 |
| VOTA | INFO | Gerando arquivo de resultado [imgbu.dat] + [Início] | 600 | 100.0 |
| VOTA | INFO | Gerando arquivo de resultado [imgbu.dat] + [Término] | 600 | 100.0 |
| VOTA | INFO | Gerando arquivo de resultado [imgze.dat] + [Início] | 600 | 100.0 |
| VOTA | INFO | Gerando arquivo de resultado [imgze.dat] + [Término] | 600 | 100.0 |
| VOTA | INFO | Gerando arquivo de resultado [hash.dat] + [Início] | 600 | 100.0 |
| VOTA | INFO | Gerando arquivo de resultado [hash.dat] + [Término] | 600 | 100.0 |
| VOTA | INFO | Gerando arquivo de resultado [wsqbio.jez] + [Início] | 600 | 100.0 |
| VOTA | INFO | Gerando arquivo de resultado [wsqbio.jez] + [Término] | 600 | 100.0 |
| VOTA | INFO | Gerando arquivo de resultado [wsqman.jez] + [Início] | 600 | 100.0 |
| VOTA | INFO | Gerando arquivo de resultado [wsqman.jez] + [Término] | 600 | 100.0 |
| VOTA | INFO | Gerando arquivo de resultado [wsqmes.jez] + [Início] | 600 | 100.0 |
| VOTA | INFO | Gerando arquivo de resultado [wsqmes.jez] + [Término] | 600 | 100.0 |
| VOTA | INFO | Gerando arquivo de resultado [mr.ver] + [Início] | 600 | 100.0 |
| VOTA | INFO | Gerando arquivo de resultado [mr.ver] + [Término] | 600 | 100.0 |
| VOTA | INFO | Gerando arquivo de resultado [log.jez] + [Início] | 600 | 100.0 |
| GAP | INFO | Verificação de assinatura - Etapa [#] - [/uenux/bin/avpart#.vst] - [SUCESSO] | 2,732 | 99.8 |
| GAP | INFO | Identificação do Modelo de Urna: UE# | 1,377 | 99.8 |
| GAP | INFO | Verificação de assinatura - Etapa [#] - [/uenux/bin/avusrbin.vst] - [SUCESSO] | 1,366 | 99.8 |
| GAP | INFO | Verificação de assinatura - Etapa [#] - [/dsk/fi/estatico/o#ba-ste.vsc] - [SUCESSO] | 1,366 | 99.8 |
| GAP | INFO | Verificação de assinatura - Etapa [#] - [/dsk/fi/estatico/o#ba-ce.vsc] - [SUCESSO] | 1,366 | 99.8 |
| GAP | INFO | Turno da UE: #º turno | 1,303 | 99.8 |
| VOTA | INFO | Início do teste de Teclado do TE | 757 | 99.8 |
| VOTA | INFO | Fim do teste de Teclado do TE - Sucesso | 756 | 99.8 |
| LOGD | INFO | Início das operações do logd | 700 | 99.8 |
| LOGD | INFO | Urna ligada em #/#/# às #:#:# | 694 | 99.8 |
| GAP | INFO | Resultado da verificação da mídia externa estática : # | 690 | 99.8 |
| GAP | INFO | Resultado da verificação da mídia externa dinâmica : # | 690 | 99.8 |
| GAP | INFO | Fase da UE: Oficial | 690 | 99.8 |
| GAP | INFO | Modo de carga da UE - Votação | 690 | 99.8 |
| GAP | INFO | Município: # | 690 | 99.8 |
| GAP | INFO | Zona Eleitoral: # | 690 | 99.8 |
| GAP | INFO | Seção Eleitoral: # | 690 | 99.8 |
| GAP | INFO | Lendo o serial da MV original a partir da MI | 690 | 99.8 |
| GAP | INFO | Lendo o serial da MV presente na urna | 690 | 99.8 |
| GAP | INFO | Data e hora da geração da mídia de votação: #/#/# #:#:# | 690 | 99.8 |
| GAP | INFO | Mídia de votação gerada pelo usuário: # | 690 | 99.8 |
| LOGD | INFO | Iniciando registro do log na MI e na ME | 689 | 99.8 |
| GAP | INFO | Estrutura de diretórios da ME: OK | 687 | 99.8 |
| GAP | INFO | Iniciando aplicação - #º turno | 687 | 99.8 |
| GAP | INFO | Versão da aplicação: #.#.#.# - Praia da Barra do Cahy | 687 | 99.8 |
| GAP | INFO | Dados carregados da geração de MR | 685 | 99.8 |
| GAP | INFO | Aplicativo presente na MR [VOTA] | 685 | 99.8 |
| GAP | INFO | Data e hora da geração da MR: #/#/# às #:#:# | 685 | 99.8 |
| GAP | INFO | MR gerada pelo usuário: # | 685 | 99.8 |
| GAP | INFO | Iniciando aplicação - ELEIÇÃO OFICIAL SEGUNDO TURNO - #º turno | 685 | 99.8 |
| GAP | INFO | Impressora OK | 684 | 99.8 |
| GAP | INFO | Mídia externa presente | 684 | 99.8 |
| GAP | INFO | Tamanho da partição estática de dados da MV: #.# MB | 684 | 99.8 |
| GAP | INFO | Tamanho da partição dinâmica de dados da MV: #.# MB | 684 | 99.8 |
| GAP | INFO | Verificação de assinatura - Etapa [#] - [/boot/boot/avboot.vst] - [SUCESSO] | 683 | 99.8 |
| GAP | INFO | Verificação de assinatura - Etapa [#] - [/boot/boot/avbootcfg.vsu] - [SUCESSO] | 683 | 99.8 |
| GAP | INFO | Verificação de assinatura - Etapa [#] - [/bin/avbin.vst] - [SUCESSO] | 683 | 99.8 |
| GAP | INFO | Verificação de assinatura - Etapa [#] - [/etc/avetc.vst] - [SUCESSO] | 683 | 99.8 |
| GAP | INFO | Verificação de assinatura - Etapa [#] - [/etc/RHVoice/avrhvoice.vst] - [SUCESSO] | 683 | 99.8 |
| GAP | INFO | Verificação de assinatura - Etapa [#] - [/share/RHVoice/languages/Brazilian-Portuguese/avsharerhvoicelang.vst] - [SUCESSO] | 683 | 99.8 |
| GAP | INFO | Verificação de assinatura - Etapa [#] - [/share/RHVoice/languages/Brazilian-Portuguese/userdict/src/avsharerhvoicelangdict.vst] - [SUCESSO] | 683 | 99.8 |
| GAP | INFO | Verificação de assinatura - Etapa [#] - [/share/RHVoice/voices/Leticia-F#/avsharerhvoiceleticia.vst] - [SUCESSO] | 683 | 99.8 |
| GAP | INFO | Verificação de assinatura - Etapa [#] - [/share/RHVoice/voices/Leticia-F#/#/avsharerhvoice#khz.vst] - [SUCESSO] | 683 | 99.8 |
| GAP | INFO | Verificação de assinatura - Etapa [#] - [/lib/modules/avmod.vst] - [SUCESSO] | 683 | 99.8 |
| GAP | INFO | Verificação de assinatura - Etapa [#] - [/lib/modules/ue#/avmodue.vst] - [SUCESSO] | 683 | 99.8 |
| VOTA | INFO | Iniciando aplicação - #º turno | 675 | 99.8 |
| VOTA | INFO | Versão da aplicação: #.#.#.# - Praia da Barra do Cahy | 675 | 99.8 |
| VOTA | INFO | Operador indagado se finaliza registro mesários | 1,477 | 99.7 |
| VOTA | ALERTA | Identificador do eleitor digitado inválido | 8,196 | 99.5 |
| VOTA | INFO | Registrando mesários antes da votação | 603 | 99.0 |
| VOTA | INFO | Batimento de digitais retornou o score # | 37,596 | 97.8 |
| VOTA | INFO | Registrando mesários após a votação | 587 | 97.8 |
| VOTA | INFO | Ano de nascimento digitado é igual ao do cadastro | 7,775 | 95.0 |
| VOTA | INFO | Biometria coletada não é do mesário # (#) | 20,444 | 90.8 |
| VOTA | INFO | Mesário # habilitou o eleitor | 7,723 | 88.3 |
| VOTA | INFO | Mesário # não é eleitor da seção | 2,735 | 87.7 |
| VOTA | INFO | Eleitor corrigiu na tela de confirmação de candidato | 1,689 | 87.3 |
| VOTA | INFO | Identificador digitado pelo mesário foi: (CPF) | 30,788 | 84.8 |
| VOTA | INFO | Timeout de reconhecimento do dedo. Tentativa [#] de [#] | 2,746 | 81.8 |
| VOTA | INFO | Justificativa recebida | 2,637 | 78.5 |
| VOTA | INFO | Espaço livre na MI [#.# GB] | 9,385 | 77.5 |
| VOTA | INFO | Quantidade de memória total [#.# GB] | 9,385 | 77.5 |
| VOTA | INFO | Quantidade de memória livre [#.# GB] | 9,385 | 77.5 |
| VOTA | INFO | Capturada a digital do mesário | 2,346 | 77.2 |
| VOTA | INFO | Não encontrou digital coletada em nenhum dos arquivos, vai salvar a digital em novo arquivo. | 2,346 | 77.2 |
| VOTA | INFO | Urna ligada conectada na rede CA em [#.#V] e na Bateria Interna com [#.#V/#A] | 8,824 | 77.0 |
| VOTA | INFO | Mesário # é eleitor da seção | 1,710 | 74.5 |
| VOTA | INFO | Biometria do mesário # encontrada nos arquivos coletados (#) | 6,008 | 72.8 |
| VOTA | INFO | Eleitor não encontrado para o identificador informado | 1,706 | 68.7 |
| VOTA | INFO | Operador cancelou o registro de mesários | 628 | 68.2 |
| VOTA | INFO | Realizada a conferência da biometria do mesário | 1,146 | 66.2 |
| VOTA | ALERTA | Digitado título inválido para o registro de mesário | 815 | 58.0 |
| VOTA | INFO | Habilitação cancelada durante confirmação de dado do eleitor | 688 | 54.3 |
| VOTA | INFO | Eleitor sem atividade por # segundos | 618 | 52.5 |
| VOTA | INFO | Digital coletada bate com uma digital gravada após o registro inicial de mesário. Não é possível associar a habilitação a um mesário. | 2,045 | 48.3 |
| VOTA | INFO | Eleitor voltou a digitar enquanto estava sendo suspenso | 467 | 46.7 |
| VOTA | INFO | Digital capturada não corresponde a digital do eleitor: Polegar Direito [score #], Polegar Esquerdo [score #], Indicador Direito [score #], Indicador Esquerdo [score #] | 508 | 42.7 |
| VOTA | INFO | Dado digitado não confere | 349 | 31.2 |
| VOTA | INFO | Urna ligada conectada na rede CA em [#.#V] e na Bateria Interna com [#.#V/#.#A] | 380 | 30.5 |
| VOTA | INFO | Solicitado ao mesário que conecte o fone de ouvido | 248 | 30.0 |
| VOTA | INFO | Solicitado ao mesário que desconecte o fone de ouvido | 248 | 30.0 |
| VOTA | INFO | Áudio desativado pelo fim da votação | 248 | 30.0 |
| VOTA | INFO | Áudio ativado conforme cadastro | 236 | 29.0 |
| VOTA | INFO | Dado digitado está incompleto | 387 | 28.2 |
| VOTA | ALERTA | Habilitação cancelada durante reconhecimento biométrico | 276 | 26.7 |
| VOTA | INFO | Urna operando na bateria interna | 489 | 25.2 |
| VOTA | INFO | Biometria coletada não é do mesário # | 2,708 | 23.8 |
| VOTA | ALERTA | O eleitor identificado já votou | 210 | 23.8 |
| VOTA | INFO | Espaço livre na MI [#.# MB] | 2,706 | 22.5 |
| VOTA | INFO | Quantidade de memória total [#.# MB] | 2,705 | 22.5 |
| VOTA | INFO | Quantidade de memória livre [#.# MB] | 2,705 | 22.5 |
| VOTA | INFO | Carga da [ALIMENTAÇÃO BATERIA INTERNA]: [PLENA] | 415 | 22.5 |
| VOTA | ALERTA | Mesário indagado se eleitor está votando | 212 | 21.5 |
| VOTA | INFO | Operador selecionou: Registrar mesários | 146 | 20.0 |
| VOTA | INFO | Mesário cancelou entrada dos dados | 144 | 18.8 |
| VOTA | INFO | Biometria do mesário # encontrada em eleitores | 1,232 | 18.0 |
| VOTA | ALERTA | Ano de nascimento digitado é diferente do cadastro | 163 | 16.8 |
| VOTA | INFO | Mesário # já registrado | 222 | 16.7 |
| VOTA | INFO | Registrando mesários durante a votação | 95 | 15.8 |
| VOTA | INFO | Eleitor está votando | 133 | 14.8 |
| VOTA | INFO | Fone de ouvido conectado | 132 | 14.0 |
| VOTA | INFO | Fone de ouvido desconectado | 129 | 13.7 |
| VOTA | INFO | Biometria do mesário # encontrada em eleitores (#) | 483 | 11.7 |
| VOTA | INFO | Operador selecionou: Ativar áudio | 70 | 10.2 |
| VOTA | INFO | Carga da [ALIMENTAÇÃO BATERIA INTERNA]: [PARCIAL] | 117 | 10.0 |
| VOTA | INFO | Habilitação cancelada durante a captura de digital do mesário | 81 | 9.3 |
| VOTA | ALERTA | Eleitor já justificou | 72 | 7.7 |
| INITJE | INFO | Urna desligada pela chave | 73 | 6.3 |
| LOGD | INFO | Fechando o arquivo de Log | 73 | 6.3 |
| VOTA | INFO | Eleitor impedido - título cancelado | 41 | 6.2 |
| VOTA | INFO | Aguardando data e hora para emissão da zerésima | 46 | 5.8 |
| VOTA | INFO | Imprimindo relatório de estado da urna | 84 | 5.3 |
| VOTA | INFO | Identificador inválido para o tipo informado | 178 | 5.0 |
| VOTA | INFO | Operador selecionou: Exibir contadores | 44 | 4.7 |
| VOTA | INFO | Urna ligada desconectada da rede CA em [#.#V] e na Bateria Interna com [#.#V/-#.#A] | 72 | 4.5 |
| VOTA | INFO | Urna ligada desconectada da rede CA em [#.#V] e na Bateria Interna com [#.#V/#.#A] | 107 | 4.2 |
| VOTA | INFO | Mudança do estado da chave: URNA DESLIGADA | 28 | 4.2 |
| VOTA | INFO | Apresentada tela do reinício da votação | 46 | 4.0 |
| VOTA | INFO | Mesário confirmou o reinício da votação | 45 | 4.0 |
| VOTA | INFO | Desligando a urna | 26 | 4.0 |
| VOTA | INFO | Finalização de aplicativo | 26 | 4.0 |
| VOTA | ALERTA | Encerramento só pode ser solicitado após as #:#:# horas | 26 | 4.0 |
| VOTA | INFO | Suspenso monitoramento de alimentação devido repetição de eventos. [ # ] eventos | 24 | 4.0 |
| VOTA | INFO | Operador cancelou o encerramento da votação | 30 | 3.8 |
| VOTA | ALERTA | Eleitor não está votando | 20 | 2.7 |
| VOTA | INFO | Solicitado título eleitoral para suspensão do eleitor | 20 | 2.7 |
| VOTA | INFO | Votação suspensa | 18 | 2.7 |
| VOTA | INFO | Áudio ativado pelo mesário | 18 | 2.5 |
| VOTA | ALERTA | Ano de nascimento inválido | 12 | 1.7 |
| VOTA | INFO | Mesário abortou processo de suspensão | 11 | 1.7 |
| VOTA | INFO | Mesário indicou reimprimir Boletim de Urna | 19 | 1.5 |
| VOTA | INFO | Mesário digitou o título para suspender o eleitor | 12 | 1.5 |
| VOTA | INFO | Todas as pessoas presentes já votaram? NÃO | 10 | 1.5 |
| VOTA | INFO | Eleitor impedido - título suspenso | 10 | 1.5 |
| VOTA | INFO | Mesário indagado se quer imprimir a zerésima | 11 | 1.3 |
| VOTA | INFO | Teste de Teclado do TE não executado | 11 | 1.2 |
| VOTA | ERRO | Não foi possível exibir imagem no LCD do terminal do mesário: Erro (#) exibindo imagem no microterminal. | 8 | 1.2 |
| VOTA | ALERTA | Procedimento de encerramento abortado | 7 | 1.2 |
| VOTA | ALERTA | Título # é válido para suspender a votação | 7 | 1.0 |
| VOTA | INFO | Eleitor foi suspenso pelo mesário | 7 | 1.0 |
| VOTA | INFO | Eleitor foi suspenso e não confirmou nenhum voto | 7 | 1.0 |

## Rotina (todos os níveis) — amostra CE: 400 de 23,765 seções

Modelos presentes em ≥ 1.0% das seções da amostra (GAP: só os 40 mais comuns). Total de modelos distintos na amostra: 1,335.

| app | nível | modelo | ocorrências | % seções |
|---|---|---|--:|--:|
| VOTA | INFO | Solicita digital. Tentativa [#] de [#] | 152,699 | 100.0 |
| VOTA | INFO | Capturada a digital. Tentativa [#] de [#] | 150,849 | 100.0 |
| VOTA | INFO | Aguardando digitação do identificador do eleitor | 113,441 | 100.0 |
| VOTA | INFO | Identificador do eleitor digitado pelo mesário | 109,173 | 100.0 |
| VOTA | INFO | Eleitor foi habilitado | 100,531 | 100.0 |
| VOTA | INFO | Voto confirmado para [Presidente] | 100,519 | 100.0 |
| VOTA | INFO | O voto do eleitor foi computado | 100,519 | 100.0 |
| VOTA | INFO | Tipo de habilitação do eleitor [biométrica] | 89,036 | 100.0 |
| VOTA | INFO | Identificador digitado pelo mesário foi: (Título de eleitor) | 75,721 | 100.0 |
| VOTA | INFO | Número de tentativas de reconhecimento do dedo. Tentativa [#] de [#] | 61,813 | 100.0 |
| VOTA | INFO | Tecla indevida pressionada | 23,282 | 100.0 |
| VOTA | INFO | Espaço livre na MV [#.# MB] | 7,915 | 100.0 |
| VOTA | INFO | Quantidade de memória usada [#.# MB] | 7,915 | 100.0 |
| VOTA | INFO | Espaço utilizado na MI [#.# MB] | 7,912 | 100.0 |
| VOTA | INFO | Espaço utilizado na MV [#.# MB] | 7,911 | 100.0 |
| VOTA | INFO | Operador confirmou o registro de mesários | 3,604 | 100.0 |
| VOTA | INFO | Pedido de leitura da biometria do mesário # | 3,181 | 100.0 |
| VOTA | INFO | Mesário # registrado | 3,085 | 100.0 |
| VOTA | INFO | Operador indagado se continua registrando mesários | 3,084 | 100.0 |
| VOTA | INFO | Inspeção da urna iniciada | 2,660 | 100.0 |
| VOTA | INFO | Inspeção da urna confirmada | 2,660 | 100.0 |
| VOTA | INFO | Inspeção da urna terminada | 2,660 | 100.0 |
| GAP | INFO | Verificação de assinatura - Etapa [#] - [/uenux/bin/avpart#.vst] - [SUCESSO] | 1,744 | 100.0 |
| VOTA | INFO | Início de impressão | 1,239 | 100.0 |
| VOTA | INFO | Fim de impressão | 1,238 | 100.0 |
| VOTA | INFO | Operador indagado se finaliza registro mesários | 1,038 | 100.0 |
| VOTA | INFO | Operador indagado se ocorrerá registro de mesários | 927 | 100.0 |
| VOTA | INFO | Operador encerrou ciclo de registro de mesários | 925 | 100.0 |
| GAP | INFO | Identificação do Modelo de Urna: UE# | 877 | 100.0 |
| GAP | INFO | Verificação de assinatura - Etapa [#] - [/uenux/bin/avusrbin.vst] - [SUCESSO] | 874 | 100.0 |
| GAP | INFO | Verificação de assinatura - Etapa [#] - [/dsk/fi/estatico/o#ce-ste.vsc] - [SUCESSO] | 872 | 100.0 |
| GAP | INFO | Verificação de assinatura - Etapa [#] - [/dsk/fi/estatico/o#ce-ce.vsc] - [SUCESSO] | 872 | 100.0 |
| GAP | INFO | Turno da UE: #º turno | 848 | 100.0 |
| VOTA | INFO | Urna operando na rede elétrica | 630 | 100.0 |
| VOTA | INFO | Início do teste de Teclado do TE | 459 | 100.0 |
| VOTA | INFO | Fim do teste de Teclado do TE - Sucesso | 459 | 100.0 |
| VOTA | INFO | Operador selecionou: Encerrar votação | 448 | 100.0 |
| LOGD | INFO | Início das operações do logd | 442 | 100.0 |
| LOGD | INFO | Urna ligada em #/#/# às #:#:# | 440 | 100.0 |
| LOGD | INFO | Iniciando registro do log na MI e na ME | 439 | 100.0 |
| GAP | INFO | Resultado da verificação da mídia externa estática : # | 439 | 100.0 |
| GAP | INFO | Resultado da verificação da mídia externa dinâmica : # | 439 | 100.0 |
| GAP | INFO | Fase da UE: Oficial | 439 | 100.0 |
| GAP | INFO | Modo de carga da UE - Votação | 439 | 100.0 |
| GAP | INFO | Município: # | 439 | 100.0 |
| GAP | INFO | Zona Eleitoral: # | 439 | 100.0 |
| GAP | INFO | Seção Eleitoral: # | 439 | 100.0 |
| GAP | INFO | Lendo o serial da MV original a partir da MI | 439 | 100.0 |
| GAP | INFO | Lendo o serial da MV presente na urna | 439 | 100.0 |
| GAP | INFO | Data e hora da geração da mídia de votação: #/#/# #:#:# | 439 | 100.0 |
| GAP | INFO | Mídia de votação gerada pelo usuário: # | 439 | 100.0 |
| GAP | INFO | Estrutura de diretórios da ME: OK | 438 | 100.0 |
| GAP | INFO | Iniciando aplicação - #º turno | 438 | 100.0 |
| GAP | INFO | Versão da aplicação: #.#.#.# - Praia da Barra do Cahy | 438 | 100.0 |
| GAP | INFO | Impressora OK | 437 | 100.0 |
| GAP | INFO | Mídia externa presente | 437 | 100.0 |
| GAP | INFO | Tamanho da partição estática de dados da MV: #.# MB | 437 | 100.0 |
| GAP | INFO | Tamanho da partição dinâmica de dados da MV: #.# MB | 437 | 100.0 |
| GAP | INFO | Verificação de assinatura - Etapa [#] - [/boot/boot/avboot.vst] - [SUCESSO] | 437 | 100.0 |
| GAP | INFO | Verificação de assinatura - Etapa [#] - [/boot/boot/avbootcfg.vsu] - [SUCESSO] | 437 | 100.0 |
| GAP | INFO | Verificação de assinatura - Etapa [#] - [/bin/avbin.vst] - [SUCESSO] | 437 | 100.0 |
| GAP | INFO | Verificação de assinatura - Etapa [#] - [/etc/avetc.vst] - [SUCESSO] | 437 | 100.0 |
| GAP | INFO | Verificação de assinatura - Etapa [#] - [/etc/RHVoice/avrhvoice.vst] - [SUCESSO] | 437 | 100.0 |
| GAP | INFO | Verificação de assinatura - Etapa [#] - [/share/RHVoice/languages/Brazilian-Portuguese/avsharerhvoicelang.vst] - [SUCESSO] | 437 | 100.0 |
| GAP | INFO | Verificação de assinatura - Etapa [#] - [/share/RHVoice/languages/Brazilian-Portuguese/userdict/src/avsharerhvoicelangdict.vst] - [SUCESSO] | 437 | 100.0 |
| GAP | INFO | Verificação de assinatura - Etapa [#] - [/share/RHVoice/voices/Leticia-F#/avsharerhvoiceleticia.vst] - [SUCESSO] | 437 | 100.0 |
| GAP | INFO | Dados carregados da geração de MR | 437 | 100.0 |
| GAP | INFO | Aplicativo presente na MR [VOTA] | 437 | 100.0 |
| GAP | INFO | MR gerada pelo computador: RCEWGEDAI# | 437 | 100.0 |
| GAP | INFO | Data e hora da geração da MR: #/#/# às #:#:# | 437 | 100.0 |
| GAP | INFO | MR gerada pelo usuário: # | 437 | 100.0 |
| GAP | INFO | Iniciando aplicação - ELEIÇÃO OFICIAL SEGUNDO TURNO - #º turno | 437 | 100.0 |
| GAP | INFO | Verificação de assinatura - Etapa [#] - [/share/RHVoice/voices/Leticia-F#/#/avsharerhvoice#khz.vst] - [SUCESSO] | 436 | 100.0 |
| GAP | INFO | Verificação de assinatura - Etapa [#] - [/lib/modules/avmod.vst] - [SUCESSO] | 436 | 100.0 |
| VOTA | INFO | Iniciando aplicação - #º turno | 434 | 100.0 |
| VOTA | INFO | Versão da aplicação: #.#.#.# - Praia da Barra do Cahy | 434 | 100.0 |
| VOTA | INFO | Operador indagado se todas as pessoas presentes votaram | 429 | 100.0 |
| VOTA | INFO | Urna pronta para receber votos | 426 | 100.0 |
| VOTA | INFO | Todas as pessoas presentes já votaram? SIM | 426 | 100.0 |
| VOTA | INFO | Imprimindo relatório [BU] via nº [#] | 410 | 100.0 |
| VOTA | INFO | Mesário indagado sobre qualidade do Boletim de Urna | 410 | 100.0 |
| VOTA | INFO | Título digitado para encerramento: # | 409 | 100.0 |
| VOTA | INFO | Imprimindo relatório [ZERÉSIMA] via nº [#] | 405 | 100.0 |
| VOTA | INFO | Imprimindo relatório [RESUMO DA ZERÉSIMA] via nº [#] | 405 | 100.0 |
| VOTA | INFO | Registrando mesários antes da votação | 404 | 100.0 |
| VOTA | INFO | Aguardando confirmação para emissão da zerésima | 401 | 100.0 |
| VOTA | INFO | Gerando relatório [ZERÉSIMA] [INÍCIO] | 401 | 100.0 |
| VOTA | INFO | Gerando relatório [ZERÉSIMA] [TÉRMINO] | 401 | 100.0 |
| VOTA | INFO | Gerando relatório [RESUMO DA ZERÉSIMA] [INÍCIO] | 401 | 100.0 |
| VOTA | INFO | Gerando relatório [RESUMO DA ZERÉSIMA] [TÉRMINO] | 401 | 100.0 |
| VOTA | INFO | Procedimento de encerramento confirmado | 400 | 100.0 |
| VOTA | INFO | Inicio do Encerramento | 400 | 100.0 |
| VOTA | INFO | Gerando relatório [BU] [INÍCIO] | 400 | 100.0 |
| VOTA | INFO | Gerando relatório [BU] [TÉRMINO] | 400 | 100.0 |
| VOTA | INFO | Gerando relatório [BUJ] [INÍCIO] | 400 | 100.0 |
| VOTA | INFO | Gerando relatório [BUJ] [TÉRMINO] | 400 | 100.0 |
| VOTA | INFO | Gerando relatório [BIM] [INÍCIO] | 400 | 100.0 |
| VOTA | INFO | Gerando relatório [BIM] [TÉRMINO] | 400 | 100.0 |
| VOTA | INFO | Gerando relatório [ELEITORES HABILITADOS BIOGRAFICAMENTE] [INÍCIO] | 400 | 100.0 |
| VOTA | INFO | Gerando relatório [ELEITORES HABILITADOS BIOGRAFICAMENTE] [TÉRMINO] | 400 | 100.0 |
| VOTA | INFO | Mesário indicou qualidade OK para Boletim de Urna | 400 | 100.0 |
| VOTA | INFO | Gerando arquivo de resultado [bu.dat] + [Início] | 400 | 100.0 |
| VOTA | INFO | Gerando arquivo de resultado [bu.dat] + [Término] | 400 | 100.0 |
| VOTA | INFO | Gerando arquivo de resultado [rdv.dat] + [Início] | 400 | 100.0 |
| VOTA | INFO | Gerando arquivo de resultado [rdv.dat] + [Término] | 400 | 100.0 |
| VOTA | INFO | Gerando arquivo de resultado [jufa.dat] + [Início] | 400 | 100.0 |
| VOTA | INFO | Gerando arquivo de resultado [jufa.dat] + [Término] | 400 | 100.0 |
| VOTA | INFO | Gerando arquivo de resultado [imgbu.dat] + [Início] | 400 | 100.0 |
| VOTA | INFO | Gerando arquivo de resultado [imgbu.dat] + [Término] | 400 | 100.0 |
| VOTA | INFO | Gerando arquivo de resultado [imgze.dat] + [Início] | 400 | 100.0 |
| VOTA | INFO | Gerando arquivo de resultado [imgze.dat] + [Término] | 400 | 100.0 |
| VOTA | INFO | Gerando arquivo de resultado [hash.dat] + [Início] | 400 | 100.0 |
| VOTA | INFO | Gerando arquivo de resultado [hash.dat] + [Término] | 400 | 100.0 |
| VOTA | INFO | Gerando arquivo de resultado [wsqbio.jez] + [Início] | 400 | 100.0 |
| VOTA | INFO | Gerando arquivo de resultado [wsqbio.jez] + [Término] | 400 | 100.0 |
| VOTA | INFO | Gerando arquivo de resultado [wsqman.jez] + [Início] | 400 | 100.0 |
| VOTA | INFO | Gerando arquivo de resultado [wsqman.jez] + [Término] | 400 | 100.0 |
| VOTA | INFO | Gerando arquivo de resultado [wsqmes.jez] + [Início] | 400 | 100.0 |
| VOTA | INFO | Gerando arquivo de resultado [wsqmes.jez] + [Término] | 400 | 100.0 |
| VOTA | INFO | Gerando arquivo de resultado [mr.ver] + [Início] | 400 | 100.0 |
| VOTA | INFO | Gerando arquivo de resultado [mr.ver] + [Término] | 400 | 100.0 |
| VOTA | INFO | Gerando arquivo de resultado [log.jez] + [Início] | 400 | 100.0 |
| VOTA | INFO | Foto do eleitor apresentada | 95,553 | 99.8 |
| VOTA | INFO | Solicitação de dado pessoal do eleitor para habilitação manual | 7,484 | 99.8 |
| VOTA | INFO | Solicita digital do mesário | 7,411 | 99.8 |
| VOTA | INFO | Dado digitado confere | 7,305 | 99.8 |
| VOTA | ALERTA | Identificador do eleitor digitado inválido | 4,717 | 98.5 |
| VOTA | INFO | Registrando mesários após a votação | 394 | 98.5 |
| VOTA | INFO | Batimento de digitais retornou o score # | 19,815 | 97.5 |
| VOTA | INFO | Identificador digitado pelo mesário foi: (CPF) | 28,539 | 94.0 |
| VOTA | INFO | Mesário # habilitou o eleitor | 5,372 | 93.5 |
| VOTA | INFO | Biometria coletada não é do mesário # (#) | 11,976 | 92.2 |
| VOTA | INFO | Mesário # não é eleitor da seção | 1,788 | 90.8 |
| VOTA | INFO | Ano de nascimento digitado é igual ao do cadastro | 4,213 | 89.5 |
| VOTA | INFO | Eleitor corrigiu na tela de confirmação de candidato | 1,318 | 87.2 |
| VOTA | INFO | Timeout de reconhecimento do dedo. Tentativa [#] de [#] | 1,781 | 82.5 |
| VOTA | INFO | Mesário # é eleitor da seção | 1,297 | 81.0 |
| VOTA | INFO | Espaço livre na MI [#.# GB] | 6,366 | 80.2 |
| VOTA | INFO | Quantidade de memória total [#.# GB] | 6,366 | 80.2 |
| VOTA | INFO | Quantidade de memória livre [#.# GB] | 6,366 | 80.2 |
| VOTA | INFO | Urna ligada conectada na rede CA em [#.#V] e na Bateria Interna com [#.#V/#A] | 6,123 | 80.2 |
| VOTA | INFO | Justificativa recebida | 1,786 | 78.5 |
| VOTA | INFO | Operador cancelou o registro de mesários | 519 | 78.5 |
| VOTA | INFO | Biometria do mesário # encontrada nos arquivos coletados (#) | 4,005 | 77.8 |
| VOTA | INFO | Realizada a conferência da biometria do mesário | 940 | 76.2 |
| VOTA | INFO | Eleitor não encontrado para o identificador informado | 822 | 71.5 |
| VOTA | INFO | Capturada a digital do mesário | 885 | 67.8 |
| VOTA | INFO | Não encontrou digital coletada em nenhum dos arquivos, vai salvar a digital em novo arquivo. | 885 | 67.8 |
| VOTA | ALERTA | Digitado título inválido para o registro de mesário | 478 | 54.2 |
| VOTA | INFO | Eleitor sem atividade por # segundos | 372 | 51.0 |
| VOTA | INFO | Habilitação cancelada durante confirmação de dado do eleitor | 374 | 48.5 |
| VOTA | INFO | Digital coletada bate com uma digital gravada após o registro inicial de mesário. Não é possível associar a habilitação a um mesário. | 1,026 | 43.2 |
| VOTA | INFO | Digital capturada não corresponde a digital do eleitor: Polegar Direito [score #], Polegar Esquerdo [score #], Indicador Direito [score #], Indicador Esquerdo [score #] | 335 | 41.8 |
| VOTA | INFO | Áudio desativado pelo fim da votação | 240 | 39.5 |
| VOTA | INFO | Solicitado ao mesário que conecte o fone de ouvido | 239 | 39.5 |
| VOTA | INFO | Solicitado ao mesário que desconecte o fone de ouvido | 239 | 39.5 |
| VOTA | INFO | Eleitor voltou a digitar enquanto estava sendo suspenso | 257 | 39.0 |
| VOTA | INFO | Áudio ativado conforme cadastro | 236 | 39.0 |
| VOTA | ALERTA | Mesário indagado se eleitor está votando | 167 | 29.2 |
| VOTA | INFO | Dado digitado está incompleto | 223 | 25.5 |
| VOTA | INFO | Operador selecionou: Registrar mesários | 120 | 25.5 |
| VOTA | INFO | Biometria coletada não é do mesário # | 1,663 | 24.8 |
| VOTA | INFO | Dado digitado não confere | 137 | 24.8 |
| VOTA | INFO | Fone de ouvido conectado | 174 | 23.8 |
| VOTA | INFO | Fone de ouvido desconectado | 174 | 23.8 |
| VOTA | INFO | Registrando mesários durante a votação | 92 | 23.0 |
| VOTA | INFO | Mesário # já registrado | 192 | 20.8 |
| VOTA | INFO | Biometria do mesário # encontrada em eleitores (#) | 481 | 20.2 |
| VOTA | INFO | Biometria do mesário # encontrada em eleitores | 886 | 20.0 |
| VOTA | INFO | Urna ligada conectada na rede CA em [#.#V] e na Bateria Interna com [#.#V/#.#A] | 174 | 20.0 |
| VOTA | INFO | Espaço livre na MI [#.# MB] | 1,549 | 19.8 |
| VOTA | INFO | Quantidade de memória total [#.# MB] | 1,549 | 19.8 |
| VOTA | INFO | Quantidade de memória livre [#.# MB] | 1,549 | 19.8 |
| VOTA | ALERTA | Habilitação cancelada durante reconhecimento biométrico | 141 | 19.8 |
| VOTA | INFO | Eleitor está votando | 99 | 19.0 |
| VOTA | INFO | Urna operando na bateria interna | 241 | 18.0 |
| VOTA | ALERTA | O eleitor identificado já votou | 119 | 17.2 |
| VOTA | INFO | Carga da [ALIMENTAÇÃO BATERIA INTERNA]: [PLENA] | 197 | 15.2 |
| VOTA | INFO | Mesário cancelou entrada dos dados | 74 | 14.2 |
| VOTA | ALERTA | Ano de nascimento digitado é diferente do cadastro | 63 | 10.5 |
| VOTA | INFO | Carga da [ALIMENTAÇÃO BATERIA INTERNA]: [PARCIAL] | 105 | 7.5 |
| INITJE | INFO | Urna desligada pela chave | 37 | 6.5 |
| LOGD | INFO | Fechando o arquivo de Log | 37 | 6.5 |
| VOTA | ALERTA | Eleitor já justificou | 32 | 6.0 |
| VOTA | INFO | Eleitor impedido - título cancelado | 28 | 6.0 |
| VOTA | INFO | Operador selecionou: Exibir contadores | 45 | 5.8 |
| VOTA | INFO | Urna ligada desconectada da rede CA em [#.#V] e na Bateria Interna com [#.#V/-#.#A] | 32 | 5.0 |
| VOTA | INFO | Habilitação cancelada durante a captura de digital do mesário | 22 | 4.8 |
| VOTA | ALERTA | Encerramento só pode ser solicitado após as #:#:# horas | 19 | 4.5 |
| VOTA | INFO | Mudança do estado da chave: URNA DESLIGADA | 21 | 4.2 |
| VOTA | INFO | Desligando a urna | 21 | 4.2 |
| VOTA | INFO | Finalização de aplicativo | 21 | 4.2 |
| VOTA | INFO | Apresentada tela do reinício da votação | 20 | 3.5 |
| VOTA | INFO | Mesário confirmou o reinício da votação | 20 | 3.5 |
| VOTA | INFO | Operador cancelou o encerramento da votação | 17 | 3.2 |
| VOTA | INFO | Eleitor impedido - título suspenso | 16 | 3.2 |
| VOTA | INFO | Votação suspensa | 14 | 3.2 |
| VOTA | INFO | Urna ligada desconectada da rede CA em [#.#V] e na Bateria Interna com [#.#V/#.#A] | 36 | 3.0 |
| VOTA | INFO | Mesário digitou o título para suspender o eleitor | 24 | 3.0 |
| VOTA | INFO | Operador selecionou: Ativar áudio | 16 | 3.0 |
| VOTA | ALERTA | Eleitor não está votando | 16 | 3.0 |
| VOTA | INFO | Solicitado título eleitoral para suspensão do eleitor | 16 | 3.0 |
| VOTA | INFO | Suspenso monitoramento de alimentação devido repetição de eventos. [ # ] eventos | 12 | 3.0 |
| VOTA | ALERTA | Título # é válido para suspender a votação | 12 | 2.8 |
| VOTA | INFO | Eleitor foi suspenso pelo mesário | 12 | 2.8 |
| VOTA | INFO | Eleitor foi suspenso e não confirmou nenhum voto | 12 | 2.8 |
| VOTA | INFO | Identificador inválido para o tipo informado | 42 | 2.5 |
| VOTA | ALERTA | Procedimento de encerramento abortado | 9 | 2.2 |
| VOTA | INFO | Aguardando data e hora para emissão da zerésima | 12 | 2.0 |
| VOTA | INFO | Imprimindo relatório de estado da urna | 17 | 1.8 |
| VOTA | INFO | Áudio ativado pelo mesário | 10 | 1.8 |
| VOTA | ALERTA | Título # é inválido para suspender a votação | 12 | 1.5 |
| VOTA | INFO | Mesário indagado se quer imprimir a zerésima | 6 | 1.5 |
| VOTA | INFO | Teste de Teclado do TE não executado | 7 | 1.2 |
| VOTA | INFO | Mesário indicou reimprimir Boletim de Urna | 10 | 1.0 |

## Eventos fora da rotina — população completa (BA: 35,476, CE: 23,765 seções)

Nível ≠ INFO, mais as mensagens INFO de interesse (fora do GAP). Ordenado por nº de seções; mostrando modelos em ≥ 0,1% das seções ou com nível ERRO/ALERTA em ≥ 10 seções.

| app | nível | modelo | ocorrências | seções | % seções |
|---|---|---|--:|--:|--:|
| LOGD | INFO | Urna ligada em #/#/# às #:#:# | 65,584 | 59,236 | 99.99 |
| GAP | ERRO | Problema ao desmontar a MR | 64,510 | 59,227 | 99.98 |
| VOTA | ALERTA | Identificador do eleitor digitado inválido | 757,869 | 59,025 | 99.64 |
| VOTA | ALERTA | Digitado título inválido para o registro de mesário | 71,997 | 33,068 | 55.82 |
| VOTA | ALERTA | Mesário indagado se eleitor está votando | 25,027 | 15,502 | 26.17 |
| VOTA | ALERTA | Habilitação cancelada durante reconhecimento biométrico | 26,027 | 13,550 | 22.87 |
| VOTA | INFO | Urna operando na bateria interna | 41,303 | 13,395 | 22.61 |
| VOTA | ALERTA | O eleitor identificado já votou | 17,227 | 10,763 | 18.17 |
| VOTA | ALERTA | Ano de nascimento digitado é diferente do cadastro | 11,608 | 8,004 | 13.51 |
| VOTA | ALERTA | Eleitor já justificou | 6,797 | 4,360 | 7.36 |
| VOTA | INFO | Eleitor impedido - título cancelado | 3,983 | 3,503 | 5.91 |
| INITJE | INFO | Urna desligada pela chave | 5,068 | 3,361 | 5.67 |
| VOTA | INFO | Mudança do estado da chave: URNA DESLIGADA | 2,607 | 2,146 | 3.62 |
| VOTA | INFO | Imprimindo relatório de estado da urna | 5,550 | 2,062 | 3.48 |
| VOTA | INFO | Desligando a urna | 2,496 | 2,055 | 3.47 |
| VOTA | INFO | Apresentada tela do reinício da votação | 3,238 | 1,995 | 3.37 |
| VOTA | INFO | Mesário confirmou o reinício da votação | 3,196 | 1,995 | 3.37 |
| VOTA | ALERTA | Encerramento só pode ser solicitado após as #:#:# horas | 2,192 | 1,912 | 3.23 |
| VOTA | INFO | Operador cancelou o encerramento da votação | 2,304 | 1,887 | 3.19 |
| VOTA | ALERTA | Eleitor não está votando | 2,142 | 1,706 | 2.88 |
| VOTA | INFO | Eleitor impedido - título suspenso | 1,889 | 1,705 | 2.88 |
| VOTA | INFO | Votação suspensa | 1,663 | 1,323 | 2.23 |
| VOTA | ALERTA | Título # é válido para suspender a votação | 1,116 | 1,040 | 1.76 |
| VOTA | INFO | Eleitor foi suspenso pelo mesário | 1,116 | 1,040 | 1.76 |
| VOTA | INFO | Eleitor foi suspenso e não confirmou nenhum voto | 1,116 | 1,040 | 1.76 |
| VOTA | INFO | Mesário indicou reimprimir Boletim de Urna | 2,181 | 975 | 1.65 |
| VOTA | ALERTA | Ano de nascimento inválido | 965 | 820 | 1.38 |
| VOTA | ALERTA | Procedimento de encerramento abortado | 714 | 694 | 1.17 |
| VOTA | INFO | Todas as pessoas presentes já votaram? NÃO | 665 | 635 | 1.07 |
| VOTA | INFO | Eleitor impedido - eleitor não tem idade mínima para votar | 506 | 401 | 0.68 |
| VOTA | INFO | Eleitor impedido - solicitou voto em trânsito | 603 | 391 | 0.66 |
| VOTA | ALERTA | Título # é inválido para suspender a votação | 722 | 382 | 0.64 |
| VOTA | ALERTA | Limite de mesários registrados atingido. Limite máximo: # | 567 | 302 | 0.51 |
| VOTA | ALERTA | Carga da [ALIMENTAÇÃO BATERIA INTERNA]: [CRÍTICA] | 702 | 292 | 0.49 |
| LOGD | INFO | Log interno da urna de contingência validado com sucesso | 331 | 291 | 0.49 |
| LOGD | INFO | Copiando conteúdo da pasta logs da MI para ME | 299 | 291 | 0.49 |
| VOTA | ERRO | Captura da digital do eleitor \| Falha na captura da digital (#) \| Ocorreu um erro durante captura da digital do eleitor. Desligue e ligue a urna. Se o erro persistir, substitua a urna. | 622 | 277 | 0.47 |
| VOTA | ERRO | Não foi possível exibir imagem no LCD do terminal do mesário: Erro (#) exibindo imagem no microterminal. | 403 | 262 | 0.44 |
| GAP | ALERTA | Bateria interna com carga crítica | 339 | 238 | 0.40 |
| VOTA | ALERTA | Eleitor não tem idade mínima | 289 | 226 | 0.38 |
| VOTA | WHAT | WHAT: virtual void api::CFingerScanner::StartAcquireImage():#:# - ERROR starting image acquisition - -# | 507 | 213 | 0.36 |
| VOTA | INFO | Eleitor impedido - vota na seção original | 405 | 179 | 0.30 |
| LOGD | INFO | Adicionando informação do log da ME | 166 | 166 | 0.28 |
| LOGD | EXTERNO | Arquivo #-#.jez referente ao log da ME | 166 | 166 | 0.28 |
| VOTA | ERRO | Erro ao tentar configurar LED do MT: Setando leds para cabine livre - # | 165 | 164 | 0.28 |
| VOTA | INFO | Eleitor impedido - eleitor convocado pela Justiça Eleitoral | 181 | 145 | 0.24 |
| LOGD | INFO | Copiando conteúdo da pasta logs da ME para a MI | 146 | 139 | 0.23 |
| VOTA | INFO | Operador confirmou que concluiu a manutenção na impressora | 983 | 137 | 0.23 |
| LOGD | ALERTA | Identificado arquivo de log corrompido na ME | 133 | 130 | 0.22 |
| LOGD | ALERTA | Arquivo #ME.jez referente ao log corrompido da ME | 133 | 130 | 0.22 |
| VOTA | INFO | Eleitor impedido - preso provisório | 128 | 74 | 0.12 |
| VOTA | ALERTA | Impressora atolada. Aguardando ação do operador | 203 | 72 | 0.12 |
| GAP | ALERTA | Bateria interna ausente | 120 | 70 | 0.12 |
| VOTA | INFO | Eleitor impedido - eleitor é militar em serviço | 95 | 67 | 0.11 |
| VOTA | ERRO | Não é possível continuar a execução \| Erro inesperado (#) \| ERROR starting image acquisition - -# Tire uma foto dessa tela em que apareça o QR Code ao lado e envie para a equipe de suporte para receber auxílio para resolução do problema. Desligue e lig | 56 | 50 | 0.08 |
| VOTA | ERRO | Erro inesperado durante a votação \| O voto do eleitor NÃO foi registrado (#) \| Ocorreu um erro enquanto o eleitor registrava suas escolhas. Desligue e ligue a urna. Se o erro persistir, tire uma foto dessa tela em que apareça o QR Code ao lado e envie | 67 | 45 | 0.08 |
| VOTA | ALERTA | Impressora com falha no corte do papel. Aguardando ação do operador | 577 | 41 | 0.07 |
| VOTA | ALERTA | Impressora sem papel. Aguardando ação do operador | 159 | 36 | 0.06 |
| GAP | ERRO | Iniciando aplicativo \| ELEIÇÃO OFICIAL SEGUNDO TURNO (#) \| Falha na execução do aplicativo. Desligue e ligue a urna. Se o erro persistir, tire uma foto dessa tela em que apareça o QR Code ao lado e envie para a equipe de suporte para receber auxílio pa | 37 | 35 | 0.06 |
| VOTA | ALERTA | Tempo limite de espera usando bateria interna atingido | 32 | 32 | 0.05 |
| VOTA | ERRO | Não é possível continuar a execução \| Erro inesperado (#) \| ERROR opening the biometric reader - -# Tire uma foto dessa tela em que apareça o QR Code ao lado e envie para a equipe de suporte para receber auxílio para resolução do problema. Desligue e l | 75 | 24 | 0.04 |
| GAP | ALERTA | Urna não testada | 39 | 21 | 0.04 |
| VOTA | ERRO | Não é possível continuar a execução \| Erro inesperado (#) \| Error ao encerrar captura - estado # (-#x#) call(#) Tire uma foto dessa tela em que apareça o QR Code ao lado e envie para a equipe de suporte para receber auxílio para resolução do problema. | 29 | 19 | 0.03 |
| VOTA | ERRO | Erro ao tentar acionar beep do TM: Tocando beeps - # | 19 | 19 | 0.03 |
| VOTA | ERRO | Não é possível continuar a execução \| Erro inesperado (#) \| Erro CFingerScanner#: last error=Erro na aquisição da imagem #x#ba#f(#) Tire uma foto dessa tela em que apareça o QR Code ao lado e envie para a equipe de suporte para receber auxílio par | 38 | 14 | 0.02 |
| VOTA | ERRO | Não é possível continuar a execução \| Erro inesperado (#) \| Device open error /dev/uescan - No such device Tire uma foto dessa tela em que apareça o QR Code ao lado e envie para a equipe de suporte para receber auxílio para resolução do problema. Desli | 23 | 13 | 0.02 |
| VOTA | ALERTA | Impressora com mecanismo aberto. Aguardando ação do operador | 71 | 12 | 0.02 |
| VOTA | ERRO | Não é possível continuar a execução \| Erro inesperado (#) \| Erro no teclado do eleitor - dispositivo desconectado Tire uma foto dessa tela em que apareça o QR Code ao lado e envie para a equipe de suporte para receber auxílio para resolução do problema | 18 | 12 | 0.02 |
| VOTA | ERRO | Não é possível continuar a execução \| Erro inesperado (#) \| ERROR OpenSession command - # Tire uma foto dessa tela em que apareça o QR Code ao lado e envie para a equipe de suporte para receber auxílio para resolução do problema. Desligue e ligue a urn | 12 | 11 | 0.02 |
| GAP | ERRO | Impressora com atolamento de papel | 10 | 10 | 0.02 |

Modelos distintos na tabela `eventos_dicionario`: 172 (lista completa: `SELECT * FROM eventos_dicionario`).
