import openai
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains
from selenium.common.exceptions import TimeoutException
import time
import easyocr
import numpy as np
from PIL import Image
import io
import requests
import re
import csv
import os
from datetime import datetime
import sqlite3

# Configurar OpenAI - substitua pela sua chave
openai.api_key = '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'

def fazer_login():
    # Configurar opções do Chrome para melhor estabilidade
    options = webdriver.ChromeOptions()
    options.add_argument('--start-maximized')
    options.add_argument('--disable-gpu')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    
    driver = webdriver.Chrome(options=options)
    
    try:
        driver.get("https://www.fgp-ead.com.br/login/index.php")
        
        username_field = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.ID, "username"))
        )
        
        username_field.clear()
        username_field.send_keys("9887")
        
        password_field = driver.find_element(By.ID, "password")
        password_field.clear()
        password_field.send_keys("36bCsSZS")
        
        login_button = driver.find_element(By.ID, "loginbtn")
        login_button.click()
        
        # Aguardar a página carregar completamente após o login
        WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "a.list-group-item"))
        )
        
        print("Login realizado com sucesso!")
        return driver
        
    except Exception as e:
        print(f"Ocorreu um erro durante o login: {str(e)}")
        driver.quit()
        return None

def init_db():
    conn = sqlite3.connect('respostas.db')
    c = conn.cursor()
    
    c.execute('''
        CREATE TABLE IF NOT EXISTS resultados (
            id INTEGER PRIMARY KEY,
            data TIMESTAMP,
            usuario TEXT,
            materia TEXT,
            semana TEXT,
            respostas TEXT,
            acertos INTEGER,
            nota REAL
        )
    ''')
    
    conn.commit()
    conn.close()

def inicializar_csv():
    """Inicializa o arquivo CSV se ele não existir"""
    arquivo = 'resultados_exercicios.csv'
    if not os.path.exists(arquivo):
        with open(arquivo, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(['Data', 'Usuario', 'Materia', 'Semana', 'Respostas', 'Acertos', 'Nota'])
    return arquivo

def registrar_resultado(usuario, materia, semana, respostas, acertos, nota):
    conn = sqlite3.connect('respostas.db')
    c = conn.cursor()
    
    c.execute('''
        INSERT INTO resultados (data, usuario, materia, semana, respostas, acertos, nota)
        VALUES (datetime('now'), ?, ?, ?, ?, ?, ?)
    ''', (usuario, materia, semana, respostas, acertos, nota))
    
    conn.commit()
    conn.close()

def get_successful_answer(materia, semana):
    conn = sqlite3.connect('respostas.db')
    c = conn.cursor()
    
    c.execute('''
        SELECT respostas, acertos 
        FROM resultados 
        WHERE materia = ? 
        AND semana = ? 
        AND acertos >= 4
        ORDER BY data DESC 
        LIMIT 1
    ''', (materia, semana))
    
    result = c.fetchone()
    conn.close()
    
    if result:
        return result[0].split(',')  # Retorna lista de respostas
    return None

def processar_semana_especifica(driver, numero_semana, guia_principal, usuario=None, materia=None):
    """Processa uma semana específica em uma matéria"""
    try:
        driver.switch_to.window(guia_principal)
        
        secoes_elementos = WebDriverWait(driver, 10).until(
            EC.presence_of_all_elements_located((By.CSS_SELECTOR, "li.section.main"))
        )
        
        for secao in secoes_elementos:
            try:
                link_secao = WebDriverWait(secao, 5).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "a.sectiontoggle"))
                )
                nome_secao = link_secao.text.strip()
                
                numero_match = re.search(r'Semana\s+(\d+)', nome_secao)
                if numero_match and int(numero_match.group(1)) == int(numero_semana):
                    try:
                        secao.find_element(By.CSS_SELECTOR, "div.availabilityinfo.isrestricted")
                        print("⚠️ Esta semana está restrita")
                        return False
                    except:
                        pass

                    try:
                        link = secao.find_element(By.CSS_SELECTOR, "a.aalink[href*='mod/lti/view.php']")
                    except:
                        try:
                            link = secao.find_element(By.CSS_SELECTOR, "a.aalink[href*='mod/quiz/view.php']")
                        except:
                            print("❌ Nenhuma atividade encontrada nesta semana")
                            return False

                    url_atividade = link.get_attribute('href')

                    # Fechar abas extras
                    abas_atuais = driver.window_handles
                    for aba in abas_atuais:
                        if aba != guia_principal:
                            driver.switch_to.window(aba)
                            driver.close()
                    
                    driver.switch_to.window(guia_principal)
                    time.sleep(2)
                    
                    driver.execute_script(f"window.open('{url_atividade}', '_blank');")
                    time.sleep(3)
                    
                    todas_abas = driver.window_handles
                    aba_atividade = None
                    
                    for aba in todas_abas:
                        if aba != guia_principal:
                            driver.switch_to.window(aba)
                            try:
                                WebDriverWait(driver, 5).until(
                                    EC.presence_of_element_located((By.CLASS_NAME, "topics-list-item"))
                                )
                                aba_atividade = aba
                                break
                            except:
                                driver.close()
                                continue
                    
                    if not aba_atividade:
                        print("❌ Não foi possível encontrar a aba correta das atividades")
                        return False
                    
                    driver.switch_to.window(aba_atividade)
                    
                    # Passar os parâmetros para acessar_topicos
                    acessar_topicos(driver, usuario, materia, numero_semana)
                    return True
                    
            except Exception as e:
                print(f"⚠️ Erro ao processar seção: {str(e)}")
                continue
        
        print(f"❌ Semana {numero_semana} não encontrada")
        return False
        
    except Exception as e:
        print(f"❌ Erro crítico ao processar semana: {str(e)}")
        return False

def processar_materias_por_semana(driver, numero_semana, usuario=None):
    """Processa todas as matérias para uma semana específica"""
    try:
        guia_principal = driver.current_window_handle
        
        print(f"\nProcessando todas as matérias para a Semana {numero_semana}")
        
        while True:
            try:
                driver.get("https://www.fgp-ead.com.br/my/")
                time.sleep(2)
                
                materias_elementos = WebDriverWait(driver, 10).until(
                    EC.presence_of_all_elements_located((By.CSS_SELECTOR, "a.list-group-item[href*='course/view.php']"))
                )
                
                materias = []
                for elemento in materias_elementos:
                    nome = elemento.find_element(By.CSS_SELECTOR, "span.media-body").text.strip()
                    if "Projeto Integrador" not in nome:
                        materias.append({
                            'nome': nome,
                            'url': elemento.get_attribute('href')
                        })
                
                for materia in materias:
                    print(f"\n{'='*50}")
                    print(f"Processando: {materia['nome']}")
                    print(f"{'='*50}")
                    
                    driver.get(materia['url'])
                    time.sleep(2)
                    
                    if not processar_semana_especifica(driver, numero_semana, guia_principal, usuario, materia['nome']):
                        print(f"⚠️ Não foi possível processar a Semana {numero_semana} em {materia['nome']}")
                    
                    fechar_guias_exceto_principal(driver, guia_principal)
                    time.sleep(2)
                
                print("\n✅ Processamento de todas as matérias concluído!")
                return True
                
            except TimeoutException:
                print("⚠️ Timeout ao carregar elementos. Tentando novamente...")
                continue
            except Exception as e:
                print(f"⚠️ Erro ao processar página: {str(e)}. Tentando novamente...")
                continue
            
    except Exception as e:
        print(f"❌ Erro crítico ao processar matérias: {str(e)}")
        return False

def enviar_resposta_desafio(driver, campo_resposta):
    try:
        print("Iniciando processo de envio da resposta do desafio...")
        
        # Lista de possíveis seletores para o botão de enviar inicial
        botoes_enviar = [
            ("xpath", "//button[contains(@class, 'challenge-finish-button')]"),
            ("xpath", "//button[contains(@class, 'v-btn--default')]//span[contains(text(), 'Enviar')]/.."),
            ("xpath", "//button[contains(text(), 'Enviar resposta')]"),
            ("xpath", "//div[contains(@class, 'challenge-footer')]//button[contains(@class, 'v-btn--default')]")
        ]
        
        # Tentar clicar no botão de enviar inicial
        botao_clicado = False
        for tipo_seletor, seletor in botoes_enviar:
            try:
                print(f"Tentando botão enviar com seletor: {seletor}")
                botao = WebDriverWait(driver, 5).until(
                    EC.element_to_be_clickable((By.XPATH, seletor))
                )
                
                driver.execute_script("arguments[0].scrollIntoView(true);", botao)
                time.sleep(1)
                
                try:
                    botao.click()
                except:
                    try:
                        driver.execute_script("arguments[0].click();", botao)
                    except:
                        ActionChains(driver).move_to_element(botao).click().perform()
                
                print("Botão de enviar inicial clicado!")
                botao_clicado = True
                break
            except:
                continue
                
        if not botao_clicado:
            print("Não foi possível encontrar o botão de enviar inicial")
            return False
            
        # Aguardar o diálogo de confirmação aparecer
        print("Aguardando diálogo de confirmação...")
        time.sleep(2)
        
        # Lista de possíveis seletores para o botão de confirmação
        confirmar_seletores = [
            ("xpath", "//div[contains(@class, 'v-dialog--active')]//button[contains(.//span, 'Enviar')]"),
            ("xpath", "//div[contains(@class, 'v-dialog--active')]//button[contains(@class, 'exercise-warning-button')]//span[contains(text(), 'Enviar')]/.."),
            ("xpath", "//div[contains(@class, 'v-dialog--active')]//button[contains(@class, 'v-btn--default')]"),
            ("css", "div.v-dialog--active button.exercise-warning-button")
        ]
        
        # Tentar clicar no botão de confirmação
        confirmacao_clicada = False
        for tipo_seletor, seletor in confirmar_seletores:
            try:
                print(f"Tentando botão confirmar com seletor: {seletor}")
                if tipo_seletor == "xpath":
                    confirmar = WebDriverWait(driver, 5).until(
                        EC.element_to_be_clickable((By.XPATH, seletor))
                    )
                else:
                    confirmar = WebDriverWait(driver, 5).until(
                        EC.element_to_be_clickable((By.CSS_SELECTOR, seletor))
                    )
                
                try:
                    confirmar.click()
                except:
                    try:
                        driver.execute_script("arguments[0].click();", confirmar)
                    except:
                        ActionChains(driver).move_to_element(confirmar).click().perform()
                
                print("Confirmação realizada com sucesso!")
                confirmacao_clicada = True
                break
            except:
                continue
        
        if not confirmacao_clicada:
            print("Não foi possível encontrar o botão de confirmação")
            return False
            
        print("Resposta do desafio enviada com sucesso!")
        return True
        
    except Exception as e:
        print(f"Erro ao enviar resposta do desafio: {str(e)}")
        return False

def enviar_resposta(driver, campo_resposta):
    try:
        print("Iniciando processo de envio da resposta...")
        
        # Lista de possíveis seletores para o botão de enviar
        botoes_enviar = [
            ("css", "button.challenge-finish-button"),
            ("css", "button.v-btn--default"),
            ("xpath", "//button[contains(text(), 'Enviar resposta')]"),
            ("xpath", "//button[contains(@class, 'challenge-finish-button')]"),
            ("xpath", "//button[contains(@class, 'v-btn') and contains(text(), 'Enviar')]")
        ]
        
        # Tentar cada seletor até encontrar o botão
        for tipo_seletor, seletor in botoes_enviar:
            try:
                print(f"Tentando seletor: {seletor}")
                if tipo_seletor == "css":
                    botao = WebDriverWait(driver, 5).until(
                        EC.element_to_be_clickable((By.CSS_SELECTOR, seletor))
                    )
                else:
                    botao = WebDriverWait(driver, 5).until(
                        EC.element_to_be_clickable((By.XPATH, seletor))
                    )
                
                # Rolar até o botão
                driver.execute_script("arguments[0].scrollIntoView(true);", botao)
                time.sleep(1)
                
                # Tentar diferentes métodos de clique
                try:
                    print("Tentando clique direto...")
                    botao.click()
                except:
                    try:
                        print("Tentando clique via JavaScript...")
                        driver.execute_script("arguments[0].click();", botao)
                    except:
                        print("Tentando clique via Action Chains...")
                        ActionChains(driver).move_to_element(botao).click().perform()
                
                print("Botão de enviar clicado com sucesso!")
                
                # Aguardar possível diálogo de confirmação
                time.sleep(2)
                
                # Tentar encontrar e clicar no botão de confirmação
                try:
                    confirmar_seletores = [
                        "//button[contains(text(), 'Confirmar')]",
                        "//button[contains(text(), 'Enviar')]",
                        "//button[contains(@class, 'v-btn') and contains(text(), 'Confirmar')]",
                        "//div[contains(@class, 'v-dialog')]//button[contains(text(), 'Enviar')]"
                    ]
                    
                    for confirmar_seletor in confirmar_seletores:
                        try:
                            confirmar = WebDriverWait(driver, 3).until(
                                EC.element_to_be_clickable((By.XPATH, confirmar_seletor))
                            )
                            confirmar.click()
                            print("Confirmação realizada!")
                            break
                        except:
                            continue
                except:
                    print("Nenhum diálogo de confirmação encontrado")
                
                return True
                
            except Exception as e:
                print(f"Erro com seletor {seletor}: {str(e)}")
                continue
        
        print("Não foi possível encontrar o botão de enviar")
        return False
        
    except Exception as e:
        print(f"Erro ao enviar resposta: {str(e)}")
        return False


def extrair_texto_imagem(driver, imagem_elemento):
    try:
        # Inicializar o EasyOCR para português
        reader = easyocr.Reader(['pt'])
        
        # Obter URL da imagem
        img_url = imagem_elemento.get_attribute('src')
        
        # Baixar a imagem
        response = requests.get(img_url)
        img = Image.open(io.BytesIO(response.content))
        
        # Converter para array numpy
        img_array = np.array(img)
        
        # Extrair texto
        resultados = reader.readtext(img_array)
        
        # Juntar todos os textos encontrados
        texto_completo = ' '.join([resultado[1] for resultado in resultados])
        
        print("Texto extraído da imagem:", texto_completo)
        return texto_completo
        
    except Exception as e:
        print(f"Erro ao extrair texto da imagem: {str(e)}")
        return ""

# def gerar_resposta_gpt(texto_desafio, texto_imagem=""):
#     try:
#         prompt = f"""
#         Responda de forma muito simples e direta:
        
#         {texto_desafio}
        
#         {f'Imagem: {texto_imagem}' if texto_imagem else ''}
        
#         - Use no máximo 300 caracteres
#         - Seja direto e objetivo
#         - Não use linguagem formal
#         """
        
#         response = openai.ChatCompletion.create(
#             model="gpt-3.5-turbo",  # Modelo mais simples e barato
#             messages=[
#                 {"role": "system", "content": "Você dá respostas curtas e diretas."},
#                 {"role": "user", "content": prompt}
#             ],
#             temperature=0.7,
#             max_tokens=150  # Reduzido para respostas mais curtas
#         )
#         return response.choices[0].message['content']
#     except Exception as e:
#         print(f"❌ Erro ao gerar resposta com GPT: {str(e)}")
#         return None

def responder_exercicios(driver, usuario, materia, semana):
   try:
       status = verificar_status_exercicios(driver)
       questoes_respondidas = 0
       respostas_dadas = []
       
       respostas_anteriores = get_successful_answer(materia, semana)
       if respostas_anteriores:
           print(f"\nEncontradas respostas anteriores bem sucedidas para {materia} - Semana {semana}")
       
       if status:
           print("\nStatus dos Exercícios:")
           print(f"Tentativas realizadas: {status['tentativas_realizadas']}/{status['tentativas_permitidas']}")
           
           if status['tentativas_realizadas'] > 0:
               print(f"Última tentativa:")
               print(f"- Acertos: {status['acertos']}")
               print(f"- Nota: {status['ultima_nota']}")
               print(f"- Data: {status['ultima_data']}")

               if status['tentativas_realizadas'] >= status['tentativas_permitidas']:
                   print("\n⚠️ Todas as tentativas já foram utilizadas!")
                   return True

               while True:
                   resposta = input("\nDeseja realizar uma nova tentativa? (s/n): ").lower()
                   if resposta in ['s', 'n']:
                       break
                   print("Por favor, responda apenas 's' ou 'n'")

               if resposta != 's':
                   print("Pulando exercícios...")
                   return True

       print("Procurando botão 'Iniciar Tentativa'...")
       seletores_iniciar = [
           ("xpath", "//button[contains(@class, 'control-button') and contains(., 'Iniciar')]"),
           ("xpath", "//div[contains(@class, 'attempts-control-buttons')]//button"),
           ("css", "button.control-button"),
           ("css", "button.v-btn.white--text"),
           ("xpath", "//button[contains(text(), 'Iniciar')]")
       ]

       botao_iniciar = None
       for tipo_seletor, seletor in seletores_iniciar:
           try:
               if tipo_seletor == "xpath":
                   botao_iniciar = WebDriverWait(driver, 5).until(
                       EC.element_to_be_clickable((By.XPATH, seletor))
                   )
               else:
                   botao_iniciar = WebDriverWait(driver, 5).until(
                       EC.element_to_be_clickable((By.CSS_SELECTOR, seletor))
                   )
               if botao_iniciar:
                   break
           except:
               continue

       if not botao_iniciar:
           print("❌ Não foi possível encontrar o botão de iniciar")
           return False

       try:
           driver.execute_script("arguments[0].scrollIntoView(true);", botao_iniciar)
           time.sleep(1)
           
           try:
               botao_iniciar.click()
           except:
               try:
                   driver.execute_script("arguments[0].click();", botao_iniciar)
               except:
                   ActionChains(driver).move_to_element(botao_iniciar).click().perform()
       except Exception as e:
           print(f"❌ Erro ao clicar no botão: {str(e)}")
           return False

       time.sleep(2)

       questao_atual = 1
       total_questoes = 5

       while questao_atual <= total_questoes:
           try:
               print(f"\nProcessando questão {questao_atual} de {total_questoes}")
               
               WebDriverWait(driver, 10).until(
                   EC.presence_of_element_located((By.CLASS_NAME, "question-content"))
               )

               time.sleep(2)

               enunciado = WebDriverWait(driver, 10).until(
                   EC.presence_of_element_located((By.CLASS_NAME, "question-text"))
               ).text
               
               opcoes = WebDriverWait(driver, 10).until(
                   EC.presence_of_all_elements_located((By.CLASS_NAME, "option-body"))
               )
               
               opcoes_texto = []
               radio_buttons = []
               for opcao in opcoes:
                   texto = opcao.find_element(By.CLASS_NAME, "question-option").text
                   radio = opcao.find_element(By.CLASS_NAME, "option-input")
                   opcoes_texto.append(texto)
                   radio_buttons.append(radio)

               if respostas_anteriores:
                   resposta = respostas_anteriores[questao_atual - 1]
                   print(f"Usando resposta anterior: {resposta}")
               else:
                   prompt = f"""
                   Analise a seguinte questão e escolha a alternativa correta:

                   Pergunta: {enunciado}

                   Opções:
                   {chr(65)}. {opcoes_texto[0]}
                   {chr(66)}. {opcoes_texto[1]}
                   {chr(67)}. {opcoes_texto[2]}
                   {chr(68)}. {opcoes_texto[3]}
                   {chr(69)}. {opcoes_texto[4]}

                   Responda apenas com a letra (A, B, C, D ou E) da alternativa correta.
                   """

                   print("Obtendo resposta via GPT...")
                   response = openai.ChatCompletion.create(
                       model="gpt-4",
                       messages=[
                           {"role": "system", "content": "Você é um especialista em sistemas de informação e desenvolvimento de software."},
                           {"role": "user", "content": prompt}
                       ],
                       temperature=0.3,
                       max_tokens=50
                   )
                   
                   resposta = response.choices[0].message['content'].strip().upper()[0]

               respostas_dadas.append(resposta)
               print(f"Resposta escolhida: {resposta}")

               indice = ord(resposta) - ord('A')
               driver.execute_script("arguments[0].scrollIntoView(true);", radio_buttons[indice])
               time.sleep(0.5)
               driver.execute_script("arguments[0].click();", radio_buttons[indice])
               print(f"✅ Opção {resposta} selecionada")
               
               questoes_respondidas += 1

               time.sleep(1)

               if questao_atual == total_questoes:
                   print("Tentando enviar respostas...")
                   enviar_btn = WebDriverWait(driver, 10).until(
                       EC.element_to_be_clickable((By.XPATH, "//button[contains(.//span, 'Enviar respostas')]"))
                   )
                   enviar_btn.click()
                   
                   time.sleep(2)
                   confirmar_btn = WebDriverWait(driver, 10).until(
                       EC.element_to_be_clickable((By.XPATH, "//div[contains(@class, 'v-dialog--active')]//button[contains(.//span, 'Enviar respostas')]"))
                   )
                   confirmar_btn.click()
                   print("✅ Respostas enviadas com sucesso!")
                   
                   time.sleep(5)
                   
                   try:
                       status_final = verificar_status_exercicios(driver)
                       if status_final:
                           acertos = status_final['acertos']
                           nota = status_final['ultima_nota']
                           
                           registrar_resultado(
                               usuario=usuario,
                               materia=materia,
                               semana=semana,
                               respostas=','.join(respostas_dadas),
                               acertos=acertos,
                               nota=nota
                           )
                           print(f"\n✅ Resultados registrados:")
                           print(f"Respostas dadas: {respostas_dadas}")
                           print(f"Acertos: {acertos}")
                           print(f"Nota: {nota}")
                   except Exception as e:
                       print(f"⚠️ Erro ao registrar resultados: {str(e)}")
               else:
                   print("Indo para próxima questão...")
                   proximo_btn = WebDriverWait(driver, 10).until(
                       EC.element_to_be_clickable((By.XPATH, "//button[contains(.//span, 'Próximo')]"))
                   )
                   proximo_btn.click()
                   print("✅ Avançou para próxima questão")

               questao_atual += 1
               time.sleep(2)

           except Exception as e:
               print(f"\n⚠️ Erro ao processar questão {questao_atual}: {str(e)}")
               return True if questoes_respondidas > 0 else False

       return True

   except Exception as e:
       print(f"\n⚠️ Erro ao processar exercícios: {str(e)}")
       return False


def clicar_proximo(driver):
    """Função auxiliar para clicar no botão próximo"""
    try:
        # Lista de possíveis seletores para o botão próximo
        seletores_proximo = [
            ("xpath", "//button[contains(@class, 'v-btn--outlined')]//span[contains(., 'Próximo')]/.."),
            ("xpath", "//button[contains(@class, 'v-btn')]//span[contains(text(), 'Próximo')]/.."),
            ("css", "button.v-btn--outlined"),
            ("xpath", "//button[contains(.//i, 'mdi-chevron-right')]"),
            ("xpath", "//div[contains(@class, 'control-buttons')]//button[last()]")
        ]

        for tipo_seletor, seletor in seletores_proximo:
            try:
                print(f"Tentando encontrar botão próximo com seletor: {seletor}")
                if tipo_seletor == "xpath":
                    botao = WebDriverWait(driver, 5).until(
                        EC.element_to_be_clickable((By.XPATH, seletor))
                    )
                else:
                    botao = WebDriverWait(driver, 5).until(
                        EC.element_to_be_clickable((By.CSS_SELECTOR, seletor))
                    )

                # Tentar diferentes métodos de clique
                try:
                    # Rolar até o botão
                    driver.execute_script("arguments[0].scrollIntoView(true);", botao)
                    time.sleep(1)

                    # Tentar clique direto
                    try:
                        botao.click()
                    except:
                        # Tentar clique via JavaScript
                        try:
                            driver.execute_script("arguments[0].click();", botao)
                        except:
                            # Tentar clique via Action Chains
                            ActionChains(driver).move_to_element(botao).click().perform()
                    
                    print("Botão próximo clicado com sucesso!")
                    return True
                except Exception as e:
                    print(f"Erro ao clicar no botão: {str(e)}")
                    continue
            except:
                continue
        
        return False
    except Exception as e:
        print(f"Erro ao tentar clicar no próximo: {str(e)}")
        return False


def verificar_e_responder_desafio(driver):
    try:
        print("\nIniciando verificação do desafio...")
        
        # Verificar se já existe uma resposta
        resposta_existente = driver.find_elements(By.CLASS_NAME, "student-answer-text")
        if resposta_existente:
            print("Desafio já foi respondido!")
            return True
            
        print("Analisando o desafio...")

        # Procurar o campo de resposta
        try:
            print("Procurando campo de resposta...")
            campo_resposta = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.ID, "text-area-answer-discursive"))
            )
        except TimeoutException:
            print("❌ Campo de resposta não encontrado!")
            return False

        # Resposta padrão para todos os desafios
        resposta = """Com base no conteúdo estudado, compreendo que este tema é complexo e envolve diversos aspectos importantes. 
        A análise dos conceitos apresentados permite estabelecer conexões significativas com a prática profissional."""

        print("Inserindo resposta no campo...")
        
        # Limpar e focar no campo
        try:
            driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", campo_resposta)
            time.sleep(1)
            campo_resposta.clear()
            campo_resposta.click()
            
            # Inserir a resposta
            for parte in resposta.split('\n'):
                campo_resposta.send_keys(parte)
                campo_resposta.send_keys('\n')
                time.sleep(0.2)
        except Exception as e:
            print(f"❌ Erro ao inserir resposta: {str(e)}")
            return False
            
        # Aguardar um pouco antes de enviar
        time.sleep(2)
        
        # Tentar enviar a resposta
        if not enviar_resposta_desafio(driver, campo_resposta):
            print("❌ Falha ao enviar a resposta")
            return False
            
        # Verificar se a resposta foi realmente enviada
        try:
            WebDriverWait(driver, 5).until(
                lambda d: len(d.find_elements(By.CLASS_NAME, "student-answer-text")) > 0
            )
            print("✅ Resposta enviada e confirmada!")
            return True
        except:
            print("⚠️ Não foi possível confirmar se a resposta foi enviada")
            return False

    except Exception as e:
        print(f"❌ Erro ao responder o desafio: {str(e)}")
        return False

def registrar_respostas_automaticamente(driver, semana):
   try:
       # Navegar para página inicial
       driver.get("https://www.fgp-ead.com.br/my/")
       time.sleep(2)

       # Pegar lista de matérias
       materias = WebDriverWait(driver, 10).until(
           EC.presence_of_all_elements_located((By.CSS_SELECTOR, "a.list-group-item[href*='course/view.php']"))
       )

       # Armazenar URLs e nomes
       materias_info = []
       for m in materias:
           nome = m.find_element(By.CSS_SELECTOR, "span.media-body").text.strip()
           url = m.get_attribute('href')
           if "Projeto Integrador" not in nome:
               materias_info.append({'nome': nome, 'url': url})

       # Processar cada matéria
       for materia in materias_info:
           print(f"\nProcessando: {materia['nome']}")
           driver.get(materia['url'])
           time.sleep(2)

           try:
               # Encontrar tópico de Exercícios na semana específica
               xpath = f"//li[contains(@class, 'section')][.//h2[contains(text(), 'Semana {semana}')]]//a[contains(@class, 'aalink')]//span[contains(@class, 'main-text') and text()='Exercícios']"
               exercicios = WebDriverWait(driver, 5).until(
                   EC.presence_of_element_located((By.XPATH, xpath))
               )

               # Clicar e mudar para nova aba
               janela_principal = driver.current_window_handle
               exercicios.click()
               time.sleep(2)

               # Mudar para nova aba
               for handle in driver.window_handles:
                   if handle != janela_principal:
                       driver.switch_to.window(handle)
                       break

               # Processar tentativas
               try:
                   tabela = WebDriverWait(driver, 10).until(
                       EC.presence_of_element_located((By.CLASS_NAME, "attempts-summary-table"))
                   )
                   tentativa = tabela.find_element(By.CSS_SELECTOR, "a.primary--text.font-weight-bold")
                   tentativa.click()
                   time.sleep(2)

                   # Coletar dados
                   acertos = driver.find_element(By.XPATH, "//td[contains(@class, 'text-center')][2]").text
                   nota = driver.find_element(By.XPATH, "//td[contains(@class, 'text-center')][3]").text

                   # Coletar respostas
                   respostas = []
                   for questao in range(5):  # 5 questões
                       alternativas = driver.find_elements(By.CLASS_NAME, "option-input")
                       for idx, alt in enumerate(alternativas):
                           if "checked" in alt.get_attribute("class"):
                               respostas.append(chr(65 + idx))
                               break

                   # Registrar resultado
                   if respostas:
                       registrar_resultado(
                           usuario="AUTO",
                           materia=materia['nome'],
                           semana=semana,
                           respostas=','.join(respostas),
                           acertos=int(acertos.split('/')[0]),
                           nota=float(nota.replace('%', ''))
                       )
                       print(f"✅ Registrado | Acertos: {acertos} | Nota: {nota}")

               except Exception as e:
                   print(f"Erro ao processar tentativa: {e}")

               # Fechar aba e voltar
               driver.close()
               driver.switch_to.window(janela_principal)

           except Exception as e:
               print(f"Erro ao processar exercícios: {e}")

       print("\nProcessamento concluído!")

   except Exception as e:
       print(f"Erro geral: {e}")

def obter_materias(driver):
    try:
        # Guardar a guia principal
        guia_principal = driver.current_window_handle
        
        # Esperar até que as matérias sejam carregadas
        materias_elementos = WebDriverWait(driver, 10).until(
            EC.presence_of_all_elements_located((By.CSS_SELECTOR, "a.list-group-item[href*='course/view.php']"))
        )
        
        materias = {}
        contador = 1
        
        print("\nMatérias disponíveis:")
        for elemento in materias_elementos:
            nome_materia = elemento.find_element(By.CSS_SELECTOR, "span.media-body").text.strip()
            
            # Ignorar o Projeto Integrador
            if "Projeto Integrador" not in nome_materia:
                materias[str(contador)] = {
                    'nome': nome_materia,
                    'url': elemento.get_attribute('href')
                }
                print(f"{contador}. {nome_materia}")
                contador += 1
        
        while True:
            escolha = input("\nDigite o número da matéria que deseja acessar (ou 'q' para sair): ")
            
            if escolha.lower() == 'q':
                return None
                
            if escolha in materias:
                materia_escolhida = materias[escolha]
                driver.get(materia_escolhida['url'])
                print(f"\nAcessando a matéria: {materia_escolhida['nome']}")
                
                while True:
                    semana = obter_semanas(driver)
                    if not semana:
                        break
                
                # Após terminar com as semanas, perguntar se quer ir para outra matéria
                while True:
                    continuar = input("\nDeseja acessar outra matéria? (s/n): ").lower()
                    if continuar in ['s', 'n']:
                        break
                    print("Por favor, responda apenas 's' ou 'n'")

                if continuar == 's':
                    # Fechar todas as guias exceto a principal
                    fechar_guias_exceto_principal(driver, guia_principal)
                    print("\nVoltar para seleção de matérias...")
                    continue
                else:
                    return None
            else:
                print("Opção inválida! Tente novamente.")
                
    except Exception as e:
        print(f"Ocorreu um erro ao listar as matérias: {str(e)}")
        return None

def fechar_guias_exceto_principal(driver, guia_principal):
    """Fecha todas as guias exceto a principal"""
    for handle in driver.window_handles:
        if handle != guia_principal:
            driver.switch_to.window(handle)
            driver.close()
    driver.switch_to.window(guia_principal)

def verificar_status_exercicios(driver):
    """Verifica o status dos exercícios e retorna informações importantes"""
    try:
        # Esperar a wrapper dos exercícios carregar
        WebDriverWait(driver, 5).until(
            EC.presence_of_element_located((By.CLASS_NAME, "exercises-wrapper"))
        )

        info = {
            'tentativas_realizadas': 0,
            'tentativas_permitidas': 0,
            'ultima_nota': 0,
            'ultima_data': '',
            'acertos': ''
        }

        # Verificar tentativas realizadas
        try:
            tentativas_elemento = driver.find_element(By.XPATH, "//div[contains(@class, 'status-info completed')]//strong[contains(text(), 'Tentativas realizadas:')]/..")
            info['tentativas_realizadas'] = int(''.join(filter(str.isdigit, tentativas_elemento.text)))
        except:
            print("Não foi possível encontrar tentativas realizadas")

        # Verificar tentativas permitidas
        try:
            permitidas_elemento = driver.find_element(By.XPATH, "//div[contains(@class, 'status-info allowed')]//strong[contains(text(), 'Tentativas permitidas:')]/..")
            info['tentativas_permitidas'] = int(''.join(filter(str.isdigit, permitidas_elemento.text)))
        except:
            print("Não foi possível encontrar tentativas permitidas")

        # Se houver tentativas realizadas, buscar informações adicionais
        if info['tentativas_realizadas'] > 0:
            try:
                tabela = driver.find_element(By.CLASS_NAME, "attempts-summary-table")
                # Pegar acertos da última tentativa
                info['acertos'] = tabela.find_element(By.XPATH, ".//td[3]").text.strip()
                # Pegar nota da última tentativa
                info['ultima_nota'] = tabela.find_element(By.XPATH, ".//td[4]").text.strip()
                # Pegar data da última tentativa
                info['ultima_data'] = tabela.find_element(By.XPATH, ".//td[5]").text.strip()
            except:
                print("Não foi possível encontrar informações detalhadas da última tentativa")

        return info

    except Exception as e:
        print(f"Erro ao verificar status dos exercícios: {str(e)}")
        return None

def obter_semanas(driver):
    try:
        # Guardar a guia principal
        guia_principal = driver.current_window_handle
        
        # Esperar até que as seções sejam carregadas
        secoes_elementos = WebDriverWait(driver, 10).until(
            EC.presence_of_all_elements_located((By.CSS_SELECTOR, "li.section.main"))
        )
        
        semanas = {}
        import re
        
        print("\nSemanas disponíveis:")
        for secao in secoes_elementos:
            try:
                # Pegar o texto do link da seção (que contém o nome da semana)
                link_secao = secao.find_element(By.CSS_SELECTOR, "a.sectiontoggle")
                nome_secao = link_secao.text.strip()
                
                if "Semana" in nome_secao:
                    # Extrair número da semana usando regex
                    numero_match = re.search(r'Semana\s+(\d+)', nome_secao)
                    if numero_match:
                        numero_semana = numero_match.group(1).zfill(2)
                        
                        try:
                            # Verificar se a seção está restrita
                            secao.find_element(By.CSS_SELECTOR, "div.availabilityinfo.isrestricted")
                            print(f"{numero_semana}. {nome_secao} (Restrito)")
                            continue  # Pular seções restritas
                        except:
                            pass

                        try:
                            # Encontrar o link da atividade (ferramenta externa)
                            link_atividade = secao.find_element(By.CSS_SELECTOR, "a.aalink[href*='mod/lti/view.php']")
                            
                            semanas[numero_semana] = {
                                'nome': nome_secao,
                                'url': link_atividade.get_attribute('href'),
                                'elemento': link_atividade
                            }
                            print(f"{numero_semana}. {nome_secao}")
                        except:
                            # Se não encontrar ferramenta externa, procurar por questionário
                            try:
                                link_atividade = secao.find_element(By.CSS_SELECTOR, "a.aalink[href*='mod/quiz/view.php']")
                                semanas[numero_semana] = {
                                    'nome': nome_secao,
                                    'url': link_atividade.get_attribute('href'),
                                    'elemento': link_atividade
                                }
                                print(f"{numero_semana}. {nome_secao}")
                            except:
                                pass
            except Exception as e:
                continue

        if not semanas:
            print("Nenhuma semana disponível encontrada.")
            return None

        while True:
            escolha = input("\nDigite o número da semana que deseja acessar (ou 'q' para sair): ")
            
            if escolha.lower() == 'q':
                return None
                
            # Garantir que a entrada tenha 2 dígitos para comparação
            escolha = escolha.zfill(2) if escolha.isdigit() else escolha
                
            if escolha in semanas:
                semana_escolhida = semanas[escolha]
                
                # Fechar todas as guias extras antes de abrir nova
                for handle in driver.window_handles:
                    if handle != guia_principal:
                        driver.switch_to.window(handle)
                        driver.close()
                
                # Voltar para a guia principal
                driver.switch_to.window(guia_principal)
                
                # Registrar as abas antes de abrir nova
                abas_antes = set(driver.window_handles)
                
                # Clicar no elemento para abrir a nova aba
                try:
                    # Tentar clicar no elemento
                    semana_escolhida['elemento'].click()
                except:
                    # Se falhar, usar JavaScript
                    driver.execute_script("arguments[0].click();", semana_escolhida['elemento'])
                
                # Aguardar nova aba abrir
                time.sleep(2)
                
                # Identificar a nova aba
                abas_depois = set(driver.window_handles)
                novas_abas = list(abas_depois - abas_antes)
                
                if novas_abas:
                    # Mudar para a última aba aberta
                    aba_atividades = novas_abas[-1]
                    driver.switch_to.window(aba_atividades)
                    
                    print(f"\nAbrindo atividade da {semana_escolhida['nome']}")
                    
                    # Aguardar a página carregar
                    try:
                        WebDriverWait(driver, 10).until(
                            EC.presence_of_element_located((By.CLASS_NAME, "topics-list-item"))
                        )
                    except:
                        print("Aviso: Aguardando carregamento da página...")
                        time.sleep(5)
                    
                    # Acessar os tópicos
                    acessar_topicos(driver)
                    
                    # Perguntar se quer continuar
                    while True:
                        continuar = input("\nDeseja acessar outra semana? (s/n): ").lower()
                        if continuar in ['s', 'n']:
                            break
                        print("Por favor, responda apenas 's' ou 'n'")

                    if continuar == 's':
                        # Fechar todas as guias exceto a principal
                        fechar_guias_exceto_principal(driver, guia_principal)
                        print("\nVoltar para seleção de semanas...")
                        continue
                    else:
                        return None
                else:
                    print("❌ Erro: Não foi possível abrir a nova aba")
                    return None
            else:
                print("Opção inválida! Tente novamente.")
                
    except Exception as e:
        print(f"Ocorreu um erro ao listar as semanas: {str(e)}")
        return None

def acessar_topicos(driver, usuario=None, materia=None, semana=None):
    try:
        topicos = [
            "Infográfico",
            "Conteúdo do Livro",
            "Dica do Professor",
            "Na prática",
            "Saiba mais",
            "Desafio",
            "Exercícios"
        ]
        
        desafio_respondido = False
        
        for idx, topico in enumerate(topicos):
            try:
                print(f"\nAcessando tópico {idx + 1}/{len(topicos)}: {topico}")
                
                if topico == "Desafio":
                    print("Preparando para acessar o Desafio...")
                    time.sleep(3)
                
                xpath = f"//a[contains(@class, 'topics-list-item')]//span[contains(@class, 'main-text') and normalize-space(text())='{topico}']/.."
                
                elemento = WebDriverWait(driver, 5).until(
                    EC.element_to_be_clickable((By.XPATH, xpath))
                )
                
                if topico == "Desafio":
                    print("Clicando no Desafio com tratamento especial...")
                    driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", elemento)
                    time.sleep(1)
                    
                    try:
                        elemento.click()
                    except:
                        try:
                            driver.execute_script("arguments[0].click();", elemento)
                        except:
                            ActionChains(driver).move_to_element(elemento).click().perform()
                    
                    time.sleep(2)
                else:
                    driver.execute_script("arguments[0].scrollIntoView(true); arguments[0].click();", elemento)
                
                print(f"Clicou em: {topico}")

                if topico == "Desafio":
                    try:
                        WebDriverWait(driver, 5).until(
                            lambda d: len(d.find_elements(By.ID, "text-area-answer-discursive")) > 0 or
                                    len(d.find_elements(By.CLASS_NAME, "student-answer-text")) > 0
                        )
                        print("Processando desafio...")
                        desafio_respondido = verificar_e_responder_desafio(driver)
                        if desafio_respondido:
                            print("✅ Desafio respondido com sucesso!")
                            time.sleep(2)
                        else:
                            print("⚠️ Falha ao responder o desafio!")
                            
                    except TimeoutException:
                        print("❌ Erro: Não foi possível carregar o desafio corretamente")

                elif topico == "Exercícios":
                    WebDriverWait(driver, 5).until(
                        lambda d: len(d.find_elements(By.CLASS_NAME, "exercises-wrapper")) > 0 or
                                len(d.find_elements(By.CLASS_NAME, "attempts-control-buttons")) > 0
                    )
                    print("Processando exercícios...")
                    exercicios_respondidos = responder_exercicios(driver, usuario, materia, str(semana))
                    if exercicios_respondidos:
                        print("✅ Exercícios respondidos com sucesso!")
                    else:
                        print("⚠️ Falha ao responder os exercícios!")

                else:
                    WebDriverWait(driver, 3).until(
                        lambda d: "topics-list-item--active" in elemento.get_attribute("class") or
                                len(d.find_elements(By.CLASS_NAME, "topic-content")) > 0
                    )

            except TimeoutException:
                print(f"⚠️ Aviso: Possível lentidão no carregamento de {topico}")
                continue
            except Exception as e:
                print(f"❌ Erro ao acessar {topico}: {str(e)}")
                continue

    except Exception as e:
        print(f"❌ Erro geral ao acessar os tópicos: {str(e)}")

def main():
    inicializar_csv()
    usuario = input("Digite seu nome de usuário: ")
    
    driver = fazer_login()
    if driver:
        time.sleep(3)
        
        while True:
            print("\nEscolha uma opção:")
            print("1. Processar uma semana específica em todas as matérias")
            print("2. Navegar por matérias individualmente")
            print("3. Sair")
            print("4. Registrar respostas automaticamente")
            
            opcao = input("\nDigite sua escolha (1-4): ")
            
            if opcao == "1":
                numero_semana = input("\nDigite o número da semana que deseja processar: ")
                if numero_semana.isdigit():
                    processar_materias_por_semana(driver, int(numero_semana), usuario)
                else:
                    print("Número de semana inválido!")
                    
            elif opcao == "2":
                while True:
                    materia = obter_materias(driver)
                    if not materia:
                        break
                    continuar = input("\nDeseja escolher outra matéria? (s/n): ")
                    if continuar.lower() != 's':
                        break
                        
            elif opcao == "3":
                break
                
            elif opcao == "4":
                numero_semana = input("\nDigite o número da semana para registrar: ")
                if numero_semana.isdigit():
                    registrar_respostas_automaticamente(driver, numero_semana)
                else:
                    print("Número de semana inválido!")
                
            else:
                print("Opção inválida!")
        
        print("\nFechando o navegador...")
        driver.quit()

if __name__ == "__main__":
    main()