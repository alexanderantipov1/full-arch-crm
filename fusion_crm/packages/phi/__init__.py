"""PHI domain — protected health information.

Access to anything inside this package is strictly mediated by ``PhiService``,
which checks principal authorisation and emits an ``AccessLog`` entry on every
read. Do NOT import models or repositories from this package directly outside
of ``packages.phi``; treat the service as the only public surface.
"""
