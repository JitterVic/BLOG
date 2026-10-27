from blog.repository.notes import NOTE_TYPE_LABELS


def test_public_notes_list_and_detail(client, app_bundle):
    _application, store = app_bundle
    store.save_note(
        {"title": "一则余笺", "type": "thought", "markdown_content": "## 片段\n\n一点记录。"},
        action="publish",
    )
    response = client.get("/api/notes?type=thought")
    assert response.status_code == 200
    payload = response.get_json()
    assert payload["total"] == 1
    assert payload["items"][0]["type_label"] == NOTE_TYPE_LABELS["thought"]

    detail = client.get("/api/notes/一则余笺")
    assert detail.status_code == 200
    assert "片段" in detail.get_json()["html_content"]


def test_admin_can_publish_note(client, app_bundle):
    from conftest import login

    csrf = login(client)
    response = client.post(
        "/admin/notes/save",
        data={
            "csrf_token": csrf,
            "title": "后台余笺",
            "type": "project",
            "markdown_content": "项目记录。",
            "action": "publish",
        },
        follow_redirects=False,
    )
    assert response.status_code == 302
    assert client.get("/api/notes?type=project").get_json()["total"] == 1