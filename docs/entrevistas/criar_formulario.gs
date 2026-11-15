/**
 * Cria no Google Forms a pesquisa descrita em formulario.md, com as seções e os desvios.
 *
 * Como usar:
 * 1. Abra https://script.google.com e clique em "Novo projeto".
 * 2. Apague o conteúdo do editor, cole este arquivo inteiro e salve.
 * 3. Escolha a função "criarFormulario" no topo e clique em "Executar".
 * 4. Autorize o acesso ao Google Forms (e ao Drive, para as imagens).
 * 5. Os links do formulário aparecem em "Registro de execução".
 *
 * Imagens: envie 02-triagem-resultado.png e 03-turno.png (de docs/prints/) para o
 * seu Google Drive antes de executar. Se não encontrar, o script segue sem elas e
 * você insere as duas à mão na seção "A ideia".
 */
function criarFormulario() {
  const form = FormApp.create('Fila na UBS: como é para você?');
  form.setDescription(
    'Somos estudantes de Engenharia de Software da FIAP e estamos criando um projeto para ' +
    'diminuir a fila nas Unidades Básicas de Saúde (UBS). Leva uns 4 minutos. A pesquisa é ' +
    'anônima: não pedimos nome, e-mail nem dado que identifique você. As respostas são usadas ' +
    'só neste trabalho acadêmico. Você pode parar quando quiser.'
  );
  form.setCollectEmail(false);
  form.setLimitOneResponsePerUser(false);
  form.setProgressBar(true);
  form.setConfirmationMessage('Obrigado! Suas respostas ajudam a desenhar uma UBS com menos fila de madrugada.');

  // ---------- Seção 1: Participação ----------
  const consentimento = form.addMultipleChoiceItem()
    .setTitle('Você concorda em responder esta pesquisa anônima para um trabalho acadêmico?')
    .setRequired(true);
  const perfil = form.addMultipleChoiceItem()
    .setTitle('Qual frase descreve você?')
    .setRequired(true);

  // ---------- Seção 2: Você e a UBS ----------
  const secaoUsuario = form.addPageBreakItem().setTitle('Você e a UBS');
  escolha(form, 'Faixa de idade', ['Até 29', '30 a 59', '60 ou mais'], true);
  escolha(form, 'Com que frequência você vai à UBS?',
    ['Uma vez por mês ou mais', 'Algumas vezes por ano', 'Uma vez por ano ou menos'], true);
  caixas(form, 'Para que você costuma ir?',
    ['Consulta', 'Receita', 'Vacina', 'Curativo', 'Exame', 'Acompanhar filho ou outra pessoa'], true);
  form.addTimeItem().setTitle('Na última vez que foi, a que horas chegou?');
  form.addTimeItem().setTitle('E a que horas foi atendido(a)?')
    .setHelpText('Se não foi atendido(a), deixe em branco.');
  form.addTextItem().setTitle('Por que chegou nesse horário?');
  escolha(form, 'Nos últimos 3 meses, quantas vezes você foi à UBS e voltou sem atendimento?',
    ['Nenhuma', '1', '2', '3 ou mais'], false);
  escolha(form, 'Você já desistiu de ir à UBS por causa da fila?',
    ['Não', 'Sim, fui à UPA ou pronto-socorro', 'Sim, fui à farmácia', 'Sim, fiquei sem atendimento'], false, true);
  caixas(form, 'O que você perdeu para esperar na fila?',
    ['Horas ou dia de trabalho', 'Precisei de alguém para ficar com filhos ou parentes', 'Outro compromisso', 'Nada'], true);

  // ---------- Seção 3: A ideia ----------
  form.addPageBreakItem().setTitle('A ideia').setHelpText(
    'Nossa ideia: você conta no celular o que está sentindo, o app diz se é caso de ir já ' +
    '(vermelho), o quanto antes (amarelo) ou de rotina (verde), e sugere o turno da UBS com ' +
    'menos fila. Ele não substitui o enfermeiro e não marca consulta: só sugere o melhor horário.'
  );
  imagemDoDrive(form, '02-triagem-resultado.png', 'Pré-triagem: o app classifica o relato por cor');
  imagemDoDrive(form, '03-turno.png', 'Turno sugerido: a previsão de cada turno, com o de menor espera marcado');
  escolha(form, 'Você usaria um app assim?', ['Sim', 'Talvez', 'Não'], true);
  form.addTextItem().setTitle('Por quê?');
  escolha(form, 'Se o app dissesse "vá às 18h, quase não tem fila", você iria nesse horário ou chegaria cedo mesmo assim?',
    ['Iria no horário sugerido', 'Chegaria cedo mesmo assim', 'Depende'], true);
  caixas(form, 'O que faria você NÃO usar?',
    ['Não tenho celular ou internet boa', 'Não confio que o horário funcione', 'Acho difícil usar chat',
     'Prefiro falar com uma pessoa', 'Nada me impediria'], true);
  form.addParagraphTextItem().setTitle('Tem algo que o app deveria fazer e não faz?');

  // ---------- Seção 4: Em uma frase ----------
  form.addPageBreakItem().setTitle('Em uma frase');
  form.addParagraphTextItem()
    .setTitle('Se tivesse que contar para alguém, em uma frase, como é a fila da sua UBS, o que diria?')
    .setHelpText('Pode ser do seu jeito. Algumas frases podem aparecer, sem identificação, na apresentação do projeto.');

  // ---------- Seção 5: Para quem trabalha em UBS ----------
  const secaoFuncionario = form.addPageBreakItem().setTitle('Para quem trabalha em UBS');
  // quem termina a seção 4 (usuário) envia o formulário em vez de seguir para a seção 5
  secaoFuncionario.setGoToPage(FormApp.PageNavigationType.SUBMIT);
  escolha(form, 'Qual é ou era a sua função?',
    ['Recepção', 'Enfermagem', 'Agente comunitário de saúde', 'Medicina', 'Gestão'], false, true);
  escolha(form, 'Há quanto tempo trabalha ou trabalhou em UBS?',
    ['Menos de 1 ano', '1 a 5 anos', 'Mais de 5 anos'], false);
  form.addParagraphTextItem().setTitle('Como funciona a distribuição de vagas ou senhas? A que horas começa a fila?');
  form.addParagraphTextItem().setTitle('Num dia cheio, quantas pessoas ficam sem atendimento, mais ou menos? Em que dias ou meses piora?');
  form.addParagraphTextItem().setTitle('Se vocês soubessem no dia anterior quantas pessoas vão vir em cada turno, o que mudariam?');
  escolha(form, 'Ver num painel quem já avisou que vem, com a cor da pré-triagem, ajudaria a recepção?',
    ['Ajudaria', 'Ajudaria pouco', 'Atrapalharia', 'Não sei'], false);
  form.addParagraphTextItem().setTitle('Uma pré-triagem por chat que NÃO substitui a classificação de risco do enfermeiro ajudaria ou atrapalharia? Por quê?');
  form.addParagraphTextItem().setTitle('O que deixaria vocês desconfiados de um sistema assim?');

  // ---------- Desvios da seção 1 (precisam das seções já criadas) ----------
  consentimento.setChoices([
    consentimento.createChoice('Sim, concordo', FormApp.PageNavigationType.CONTINUE),
    consentimento.createChoice('Não', FormApp.PageNavigationType.SUBMIT),
  ]);
  perfil.setChoices([
    perfil.createChoice('Fui atendido(a) em uma UBS nos últimos 12 meses', secaoUsuario),
    perfil.createChoice('Trabalho ou trabalhei em uma UBS', secaoFuncionario),
    perfil.createChoice('Nenhuma das duas', FormApp.PageNavigationType.SUBMIT),
  ]);

  Logger.log('Editar: ' + form.getEditUrl());
  Logger.log('Link para enviar: ' + form.shortenFormUrl(form.getPublishedUrl()));
}

function escolha(form, titulo, opcoes, obrigatoria, outro) {
  const item = form.addMultipleChoiceItem().setTitle(titulo).setChoiceValues(opcoes).setRequired(obrigatoria);
  if (outro) item.showOtherOption(true);
  return item;
}

function caixas(form, titulo, opcoes, outro) {
  const item = form.addCheckboxItem().setTitle(titulo).setChoiceValues(opcoes);
  if (outro) item.showOtherOption(true);
  return item;
}

function imagemDoDrive(form, nomeArquivo, legenda) {
  const arquivos = DriveApp.getFilesByName(nomeArquivo);
  if (!arquivos.hasNext()) {
    Logger.log('Imagem não encontrada no Drive: ' + nomeArquivo + ' (insira à mão na seção "A ideia")');
    return;
  }
  form.addImageItem().setImage(arquivos.next().getBlob()).setTitle(legenda);
}
