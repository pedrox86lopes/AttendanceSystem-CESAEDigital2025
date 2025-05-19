import random
from faker import Faker
from datetime import datetime, timedelta
from django.core.management.base import BaseCommand
from django.utils import timezone
from Gestao.models import Utilizador, Curso, Modulo, Aula, RegistoPresenca

class Command(BaseCommand):
    help = 'Popula a base de dados com utilizadores, curso, módulos, aulas e registos de presença.'

    def handle(self, *args, **kwargs):
        fake = Faker('pt_PT')

        # --- Gerar formadores ---
        formadores = []
        for _ in range(3):
            first = fake.first_name()
            last = fake.last_name()
            username = f"{first}.{last}.PRT.Formador"
            email = f"{first.lower()}.{last.lower()}@cesae.pt"
            formadores.append({
                "username": username,
                "first_name": first,
                "last_name": last,
                "email": email,
                "tipo": "Formador"
            })

        # --- Gerar formandos ---
        formandos = []
        for _ in range(10):
            first = fake.first_name()
            last = fake.last_name()
            nif = fake.unique.random_int(min=100000000, max=999999999)
            username = f"{first}.{last}.{nif}"
            email = f"{first.lower()}.{last.lower()}@formando.cesae.pt"
            formandos.append({
                "username": username,
                "first_name": first,
                "last_name": last,
                "nif": nif,
                "email": email,
                "tipo": "Formando"
            })

        # --- Criar Utilizadores ---
        for u in formadores + formandos:
            Utilizador.objects.create_user(
                username=u["username"],
                first_name=u["first_name"],
                last_name=u["last_name"],
                email=u["email"],
                password="12345678",
                tipo=u["tipo"]
            )

        # --- Criar curso ---
        curso_data = {
            "nome": "Software Developer",
            "descricao": "Curso de formação CESAE Digital para desenvolvimento de software.",
            "carga_horaria_total": 1020
        }
        curso_obj = Curso.objects.create(**curso_data)

        # --- Criar módulos ---
        modulos_nomes = [
            "Engenharia de software",
            "Bases de dados - conceitos",
            "Programação em SQL",
            "Programação - Algoritmos",
            "Programação de computadores - estruturada",
            "Programação de computadores - orientada a objetos",
            "Programação para a WEB - cliente (client-side)",
            "Programação para a WEB - servidor (server-side)",
            "Integração de sistemas de informação - conceitos",
            "Integração de sistemas de informação - tecnologias e níveis de Integração",
            "Integração de sistemas de informação - ferramentas",
            "Acesso móvel a sistemas de informação",
            "Desenvolvimento de aplicações mobile",
            "Projeto de tecnologias e programação de sistemas de informação",
            "Inglês técnico aplicado às telecomunicações",
            "Comunicação assertiva e técnicas de procura de emprego"
        ]

        modulos = []
        for i, nome in enumerate(modulos_nomes):
            carga = random.randint(40, 80) if i < len(modulos_nomes) - 1 else 1020 - sum([mod.carga_horaria for mod in modulos])
            formador = Utilizador.objects.filter(tipo="Formador").order_by("?").first()
            mod = Modulo.objects.create(
                curso=curso_obj,
                nome=f"Mód. {i+1} {nome}",
                descricao=f"Módulo sobre {nome.lower()} no contexto do desenvolvimento de software.",
                carga_horaria=carga,
                formador=formador
            )
            modulos.append(mod)

        # --- Criar aulas e presenças ---
        aulas = []
        registos_presenca = []
        start_date = datetime(2024, 1, 1)

        for modulo in modulos:
            for _ in range(random.randint(3, 6)):
                dias_aleatorios = random.randint(1, 30)
                data = start_date + timedelta(days=dias_aleatorios)
                periodo = random.choice(['manha', 'tarde'])

                aula_obj = Aula.objects.create(
                    modulo=modulo,
                    data=data.date(),
                    periodo=periodo
                )
                aulas.append(aula_obj)

                for formando in Utilizador.objects.filter(tipo="Formando"):
                    presente = random.choice([True, False, True])
                    if presente:
                        entrada = datetime.combine(data.date(), datetime.min.time()) + timedelta(hours=9, minutes=random.randint(0, 15))
                        saida = entrada + timedelta(hours=3)
                        registos_presenca.append({
                            "formando": formando,
                            "aula": aula_obj,
                            "entrada": entrada,
                            "saida": saida,
                            "motivo_atraso": "" if entrada.hour <= 9 else "Chegada tardia devido a transporte.",
                            "falta_justificada": False
                        })
                    else:
                        registos_presenca.append({
                            "formando": formando,
                            "aula": aula_obj,
                            "entrada": None,
                            "saida": None,
                            "motivo_atraso": "",
                            "falta_justificada": random.choice([False, True])
                        })

        for registo in registos_presenca:
            RegistoPresenca.objects.create(
                formando=registo["formando"],
                aula=registo["aula"],
                entrada=registo["entrada"],
                saida=registo["saida"],
                motivo_atraso=registo["motivo_atraso"],
                falta_justificada=registo["falta_justificada"]
            )

        self.stdout.write(self.style.SUCCESS("Base de dados populada com sucesso!"))
