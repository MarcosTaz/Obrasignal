import test from 'node:test';
import assert from 'node:assert/strict';
import {makeNeonSessionAdapter,NEON_AUTH_BASE} from './neon-session-adapter.mjs';

test('sign in is cookie-bound and yields no bearer token',async()=>{
 let request;
 const client=makeNeonSessionAdapter({fetcher:async (url,opts)=>{request={url,opts};return{ok:true,status:200,json:async()=>({user:{id:'id',email:'synthetic@example.com'},token:'opaque'})}}});
 assert.deepEqual(await client.signIn(' TEST@EXAMPLE.COM ','not-a-real-password'),{ok:true});
 assert.equal(request.url,NEON_AUTH_BASE+'/sign-in/email');
 assert.equal(request.opts.credentials,'include');
 assert.equal(JSON.parse(request.opts.body).email,'test@example.com');
 assert.deepEqual(await client.getSession(),{authenticated:true,user:{id:'id',email:'synthetic@example.com'}});
 await assert.rejects(()=>client.authorizationHeader(),/not_yet_verified/);
});
test('unsigned or missing identity never establishes session',async()=>{
 const client=makeNeonSessionAdapter({fetcher:async()=>({ok:true,status:200,json:async()=>({token:'untrusted'})})});
 assert.deepEqual(await client.getSession(),{authenticated:false});
});
test('signout calls only trusted Neon provider; errors fail closed',async()=>{
 const paths=[];
 const client=makeNeonSessionAdapter({fetcher:async(url,opts)=>{paths.push({url,opts});return{ok:false,status:401}}});
 assert.deepEqual(await client.signOut(),{ok:false});
 assert.equal(paths[0].url,NEON_AUTH_BASE+'/sign-out');
 assert.throws(()=>makeNeonSessionAdapter({baseUrl:'https://evil.example'}),/untrusted/);
 assert.deepEqual(await client.getSession(),{authenticated:false});
});

test('candidate token is never mistaken for already-authorized API access',async()=>{
 const seen=[];
 const client=makeNeonSessionAdapter({fetcher:async url=>{
   seen.push(url);
   if(url.endsWith('/get-session')) return {ok:true,status:200,json:async()=>({user:{id:'test',email:'synthetic@example.com'}})};
   return {ok:true,status:200,json:async()=>({token:'a.b.c'})};
 }});
 assert.equal(await client.candidateJwt(),'a.b.c');
 assert.ok(seen.includes(NEON_AUTH_BASE+'/token'));
 await assert.rejects(()=>client.authorizationHeader(),/not_yet_verified/);
});
test('no candidate token for signed-out users',async()=>{
 let calls=0;
 const client=makeNeonSessionAdapter({fetcher:async()=>{
   calls++;return {ok:true,status:200,json:async()=>({user:null})};
 }});
 assert.equal(await client.candidateJwt(),null);
 assert.equal(calls,1);
});
