from flask import Flask, render_template, request, redirect, url_for, flash
from abc import ABC, abstractmethod
from datetime import datetime
import json
import os

app = Flask(__name__)
app.secret_key = "chave-local-etapa6"

ARQUIVO_DADOS = os.path.join(os.path.dirname(__file__), "dados_bancarios.json")


class Transacao:
    """Representa uma movimentação individual da conta."""
    def __init__(self, tipo, valor, data=None, descricao=""):
        self.tipo = tipo.upper()
        self.valor = float(valor)
        self.data = data or datetime.now().isoformat(timespec="seconds")
        self.descricao = descricao

    def para_dict(self):
        return {
            "tipo": self.tipo,
            "valor": self.valor,
            "data": self.data,
            "descricao": self.descricao
        }

    @classmethod
    def de_dict(cls, dados):
        return cls(
            dados["tipo"], dados["valor"],
            dados.get("data"), dados.get("descricao", "")
        )


class Cliente:
    def __init__(self, nome, cpf, salario=0.0, telefone=""):
        self.nome = nome
        self.cpf = cpf
        self.salario = float(salario)
        self.telefone = telefone
        self.contas = []

    def calcular_patrimonio(self):
        return sum(conta.saldo for conta in self.contas)


class Conta(ABC):
    def __init__(self, numero, cliente, saldo=0.0):
        self.numero = int(numero)
        self.cliente = cliente
        self.saldo = float(saldo)
        self.historico_transacoes = []

    def registrar_transacao(self, tipo, valor, descricao=""):
        self.historico_transacoes.append(Transacao(tipo, valor, descricao=descricao))

    def depositar(self, valor):
        valor = float(valor)
        if valor <= 0:
            return False, "O depósito deve ser maior que zero."
        self.saldo += valor
        self.registrar_transacao("DEPOSITO", valor, "Depósito em conta")
        return True, f"Depósito de R$ {valor:.2f} realizado."

    def sacar(self, valor):
        valor = float(valor)
        if valor <= 0:
            return False, "O saque deve ser maior que zero."
        if valor > self.saldo:
            return False, "Saldo insuficiente."
        self.saldo -= valor
        self.registrar_transacao("SAQUE", valor, "Saque em conta")
        return True, f"Saque de R$ {valor:.2f} realizado."

    def transferir(self, valor, conta_destino):
        valor = float(valor)
        if conta_destino.numero == self.numero:
            return False, "A conta de destino deve ser diferente da origem."
        if valor <= 0:
            return False, "A transferência deve ser maior que zero."
        if valor > self.saldo:
            return False, "Saldo insuficiente."
        self.saldo -= valor
        conta_destino.saldo += valor
        self.registrar_transacao("PIX_ENVIADO", valor, f"Transferência para conta {conta_destino.numero}")
        conta_destino.registrar_transacao("PIX_RECEBIDO", valor, f"Transferência da conta {self.numero}")
        return True, f"Transferência de R$ {valor:.2f} realizada."

    @abstractmethod
    def tipo_conta(self):
        pass

    def exibir_historico(self):
        return self.historico_transacoes


class ContaCorrente(Conta):
    def __init__(self, numero, cliente, saldo=0.0, taxa_manutencao=0.0):
        super().__init__(numero, cliente, saldo)
        self.taxa_manutencao = float(taxa_manutencao)

    def tipo_conta(self):
        return "Corrente"

    def descontar_taxa_manutencao(self):
        if self.taxa_manutencao <= 0:
            return False, "Taxa de manutenção não configurada."
        if self.saldo < self.taxa_manutencao:
            return False, "Saldo insuficiente para descontar a taxa."
        self.saldo -= self.taxa_manutencao
        self.registrar_transacao("TAXA_MANUTENCAO", self.taxa_manutencao, "Taxa de manutenção")
        return True, f"Taxa de R$ {self.taxa_manutencao:.2f} descontada."


class ContaPoupanca(Conta):
    def __init__(self, numero, cliente, saldo=0.0, taxa_rendimento=0.0):
        super().__init__(numero, cliente, saldo)
        self.taxa_rendimento = float(taxa_rendimento)

    def tipo_conta(self):
        return "Poupança"

    def aplicar_rendimento(self):
        if self.taxa_rendimento <= 0:
            return False, "Taxa de rendimento não configurada."
        rendimento = self.saldo * (self.taxa_rendimento / 100)
        if rendimento <= 0:
            return False, "Não há saldo para aplicar rendimento."
        self.saldo += rendimento
        self.registrar_transacao("RENDIMENTO", rendimento, "Rendimento da poupança")
        return True, f"Rendimento de R$ {rendimento:.2f} aplicado."


class Agencia:
    def __init__(self, numero="001", nome="Agência UFS"):
        self.numero = numero
        self.nome = nome
        self.contas = []

    def adicionar_conta(self, conta):
        self.contas.append(conta)

    def buscar_conta(self, numero):
        for conta in self.contas:
            if conta.numero == int(numero):
                return conta
        return None

    def calcular_patrimonio(self):
        return sum(conta.saldo for conta in self.contas)


class Banco:
    def __init__(self):
        self.clientes = []
        self.agencia = Agencia()
        self.proxima_conta = 1

    def cadastrar_cliente(self, nome, cpf, salario=0, telefone=""):
        if not nome.strip() or not cpf.strip():
            return False, "Nome e CPF são obrigatórios."
        if any(c.cpf == cpf.strip() for c in self.clientes):
            return False, "Já existe cliente com esse CPF."
        try:
            cliente = Cliente(nome.strip(), cpf.strip(), salario or 0, telefone.strip())
        except ValueError:
            return False, "Salário inválido."
        self.clientes.append(cliente)
        return True, "Cliente cadastrado com sucesso."

    def buscar_cliente(self, cpf):
        return next((c for c in self.clientes if c.cpf == cpf), None)

    def cadastrar_conta(self, cpf, tipo):
        cliente = self.buscar_cliente(cpf)
        if not cliente:
            return False, "Cliente não encontrado."
        numero = self.proxima_conta
        if tipo == "Corrente":
            conta = ContaCorrente(numero, cliente)
        elif tipo == "Poupança":
            conta = ContaPoupanca(numero, cliente)
        else:
            return False, "Tipo de conta inválido."
        self.proxima_conta += 1
        self.agencia.adicionar_conta(conta)
        cliente.contas.append(conta)
        return True, f"Conta {numero} ({tipo}) cadastrada."

    def para_dict(self):
        clientes_json = []
        for cliente in self.clientes:
            contas_json = []
            for conta in cliente.contas:
                conta_json = {
                    "numero": conta.numero,
                    "tipo": conta.tipo_conta(),
                    "saldo": conta.saldo,
                    "historico_transacoes": [t.para_dict() for t in conta.historico_transacoes]
                }
                if isinstance(conta, ContaCorrente):
                    conta_json["taxa_manutencao"] = conta.taxa_manutencao
                elif isinstance(conta, ContaPoupanca):
                    conta_json["taxa_rendimento"] = conta.taxa_rendimento
                contas_json.append(conta_json)
            clientes_json.append({
                "nome": cliente.nome,
                "cpf": cliente.cpf,
                "salario": cliente.salario,
                "telefone": cliente.telefone,
                "contas": contas_json
            })
        return [{
            "numero": self.agencia.numero,
            "nome": self.agencia.nome,
            "clientes": clientes_json
        }]

    @classmethod
    def de_dados(cls, dados):
        banco = cls()
        if not dados:
            return banco
        agencia_dados = dados[0]
        banco.agencia = Agencia(agencia_dados.get("numero", "001"), agencia_dados.get("nome", "Agência UFS"))
        maior_numero = 0
        for cliente_dados in agencia_dados.get("clientes", []):
            cliente = Cliente(
                cliente_dados["nome"], cliente_dados["cpf"],
                cliente_dados.get("salario", 0), cliente_dados.get("telefone", "")
            )
            banco.clientes.append(cliente)
            for conta_dados in cliente_dados.get("contas", []):
                numero = int(conta_dados["numero"])
                tipo = conta_dados["tipo"]
                saldo = float(conta_dados.get("saldo", 0))
                if tipo == "Corrente":
                    conta = ContaCorrente(numero, cliente, saldo, conta_dados.get("taxa_manutencao", 0))
                else:
                    conta = ContaPoupanca(numero, cliente, saldo, conta_dados.get("taxa_rendimento", 0))
                conta.historico_transacoes = [
                    Transacao.de_dict(t) for t in conta_dados.get("historico_transacoes", [])
                ]
                cliente.contas.append(conta)
                banco.agencia.adicionar_conta(conta)
                maior_numero = max(maior_numero, numero)
        banco.proxima_conta = maior_numero + 1
        return banco


def salvar_dados_bancarios(banco, nome_arquivo=ARQUIVO_DADOS):
    """Converte os objetos em dicionários e grava o JSON no disco."""
    with open(nome_arquivo, "w", encoding="utf-8") as arquivo:
        json.dump(banco.para_dict(), arquivo, indent=4, ensure_ascii=False)


def carregar_dados_bancarios(nome_arquivo=ARQUIVO_DADOS):
    """Lê o JSON e reconstrói os objetos Cliente, Conta e Transacao."""
    if not os.path.exists(nome_arquivo):
        return Banco()
    with open(nome_arquivo, "r", encoding="utf-8") as arquivo:
        dados = json.load(arquivo)
    return Banco.de_dados(dados)


banco = carregar_dados_bancarios()


@app.route("/", methods=["GET", "POST"])
def inicio():
    if request.method == "POST":
        acao = request.form.get("acao")
        try:
            if acao == "cliente":
                ok, msg = banco.cadastrar_cliente(
                    request.form.get("nome", ""),
                    request.form.get("cpf", ""),
                    request.form.get("salario", "0"),
                    request.form.get("telefone", "")
                )
            elif acao == "conta":
                ok, msg = banco.cadastrar_conta(
                    request.form.get("cpf", ""),
                    request.form.get("tipo", "")
                )
            elif acao in ("deposito", "saque"):
                conta = banco.agencia.buscar_conta(request.form.get("numero", ""))
                if not conta:
                    ok, msg = False, "Conta não encontrada."
                elif acao == "deposito":
                    ok, msg = conta.depositar(request.form.get("valor", "0"))
                else:
                    ok, msg = conta.sacar(request.form.get("valor", "0"))
            elif acao == "transferencia":
                origem = banco.agencia.buscar_conta(request.form.get("origem", ""))
                destino = banco.agencia.buscar_conta(request.form.get("destino", ""))
                if not origem or not destino:
                    ok, msg = False, "Conta de origem ou destino não encontrada."
                else:
                    ok, msg = origem.transferir(request.form.get("valor", "0"), destino)
            elif acao == "salvar":
                salvar_dados_bancarios(banco)
                ok, msg = True, "Dados salvos no arquivo JSON."
            else:
                ok, msg = False, "Operação desconhecida."
        except (ValueError, TypeError):
            ok, msg = False, "Confira os números e valores informados."

        if ok and acao != "salvar":
            salvar_dados_bancarios(banco)
        flash(msg, "sucesso" if ok else "erro")
        return redirect(url_for("inicio"))

    return render_template(
        "index.html",
        banco=banco,
        clientes=banco.clientes,
        contas=banco.agencia.contas,
        patrimonio=banco.agencia.calcular_patrimonio()
    )


if __name__ == "__main__":
    app.run(debug=True)
