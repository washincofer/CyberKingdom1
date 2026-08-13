# Subir no repositório CyberKingdom

## Via interface do GitHub

1. Descompacte o pacote.
2. Entre no repositório `CyberKingdom`.
3. Use **Add file → Upload files**.
4. Envie o conteúdo desta pasta (não a pasta externa do ZIP).
5. Sugestão de mensagem: `feat: add SQLite VS-001 backend prototype`.

## Via Git

```bash
git clone <URL-DO-REPOSITORIO-CyberKingdom>
cd CyberKingdom
cp -R /caminho/CyberKingdom_GitHub_SQLitePrototype_v0.1/. .
git checkout -b dev/sqlite-vs001
git add .
git commit -m "feat: add SQLite VS-001 backend prototype"
git push -u origin dev/sqlite-vs001
```

Depois, abra um Pull Request para `main` ou para a branch de desenvolvimento adotada pelo projeto.
