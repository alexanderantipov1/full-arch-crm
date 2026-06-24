"""Marketing domain — ad-spend and campaign metrics from ad platforms.

Aggregate (non-person) marketing data pulled read-only from Google Ads,
Meta Ads, and TikTok Ads. Person-linked marketing signals (leads, calls,
SMS) live in ``identity`` / ``ops`` / ``interaction`` — NOT here.

Public surface is :class:`packages.marketing.service.MarketingService`.
Do not import models or the repository from outside this package.
"""
