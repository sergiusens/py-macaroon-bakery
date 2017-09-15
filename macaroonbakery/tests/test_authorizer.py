# Copyright 2017 Canonical Ltd.
# Licensed under the LGPLv3, see LICENCE file for details.
from unittest import TestCase

from macaroonbakery.identity import Identity, SimpleIdentity, ACLIdentity
from macaroonbakery import checkers
from macaroonbakery.authorizer import AuthorizerFunc, ACLAuthorizer, EVERYONE
from macaroonbakery.checker import Op


class TestAuthorizer(TestCase):
    def test_authorize_func(self):
        def f(ctx, identity, op):
            self.assertEqual(identity.id(), 'bob')
            if op.entity == 'a':
                return False, None
            elif op.entity == 'b':
                return True, None
            elif op.entity == 'c':
                return True, [checkers.Caveat(location='somewhere',
                                              condition='c')]
            elif op.entity == 'd':
                return True, [checkers.Caveat(location='somewhere',
                                              condition='d')]
            else:
                self.fail('unexpected entity: ' + op.Entity)

        ops = [Op('a', 'x'), Op('b', 'x'), Op('c', 'x'), Op('d', 'x')]
        allowed, caveats = AuthorizerFunc(f).authorize(
            checkers.AuthContext(),
            SimpleIdentity('bob'),
            *ops
        )
        self.assertEqual(allowed, [False, True, True, True])
        self.assertEqual(caveats, [
            checkers.Caveat(location='somewhere', condition='c'),
            checkers.Caveat(location='somewhere', condition='d')
        ])

    def test_acl_authorizer(self):
        ctx = checkers.AuthContext()
        tests = [
            ('no ops, no problem',
             ACLAuthorizer(allow_public=True,
                           get_acl=lambda x, y: []), None, [], []),
            ('identity that does not implement ACLIdentity; '
             'user should be denied except for everyone group',
             ACLAuthorizer(allow_public=True,
                           get_acl=lambda ctx, op: [EVERYONE]
                           if op.entity == 'a' else ['alice']),
             SimplestIdentity('bob'),
             [Op(entity='a', action='a'), Op(entity='b', action='b')],
             [True, False]),
            ('identity that does not implement ACLIdentity with user == Id; '
             'user should be denied except for everyone group',
             ACLAuthorizer(allow_public=True,
                           get_acl=lambda ctx, op: [EVERYONE] if
                           op.entity == 'a' else ['bob']),
             SimplestIdentity('bob'),
             [Op(entity='a', action='a'), Op(entity='b', action='b')],
             [True, False]),
            ('permission denied for everyone without AllowPublic',
             ACLAuthorizer(allow_public=False,
                           get_acl=lambda x, y: [EVERYONE]),
             SimplestIdentity('bob'),
             [Op(entity='a', action='a')],
             [False]),
            ('permission granted to anyone with no identity with AllowPublic',
             ACLAuthorizer(allow_public=True,
                           get_acl=lambda x, y: [EVERYONE]),
             None,
             [Op(entity='a', action='a')],
             [True])
        ]
        for test in tests:
            allowed, caveats = test[1].authorize(ctx, test[2], *test[3])
            self.assertEqual(len(caveats), 0)
            self.assertEqual(allowed, test[4])

    def test_context_wired_properly(self):
        ctx = checkers.AuthContext({'a': 'aval'})

        class Visited:
            in_f = False
            in_allow = False
            in_get_acl = False

        def f(ctx, identity, op):
            self.assertEqual(ctx.get('a'), 'aval')
            Visited.in_f = True
            return False, None
        AuthorizerFunc(f).authorize(ctx, SimpleIdentity('bob'), ['op1'])
        self.assertTrue(Visited.in_f)

        class TestIdentity(SimplestIdentity, ACLIdentity):
            def allow(other, ctx, acls):
                self.assertEqual(ctx.get('a'), 'aval')
                Visited.in_allow = True
                return False

        def get_acl(ctx, acl):
            self.assertEqual(ctx.get('a'), 'aval')
            Visited.in_get_acl = True
            return []
        ACLAuthorizer(allow_public=False,
                      get_acl=get_acl).authorize(ctx,
                                                 TestIdentity('bob'),
                                                 ['op1'])
        self.assertTrue(Visited.in_get_acl)
        self.assertTrue(Visited.in_allow)


class SimplestIdentity(Identity):
    # SimplestIdentity implements Identity for a string. Unlike
    # SimpleIdentity, it does not implement ACLIdentity.
    def __init__(self, user):
        self._identity = user

    def domain(self):
        return ''

    def id(self):
        return self._identity