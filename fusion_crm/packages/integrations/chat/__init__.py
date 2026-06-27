"""Chat provider layer (ENG-436, Interactive Corporate Messenger).

Block C owns the ``ChatProvider`` interface, the resolver hook, and the
default notification-rule seed. Provider adapters (Mattermost, …) live in
their own modules and are wired through :func:`resolve_chat_provider`.

Block D (ENG-437) adds the rule engine: the canonical event taxonomy
(``events``), the condition predicate engine (``conditions``), the
de-identified template renderer (``render``), and the
``NotificationEventService`` (``event_service``) that ties them together
into ``emit(tenant_id, event_type, context)``.
"""
