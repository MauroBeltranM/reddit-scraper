import{t as e}from"./api-CCWHsAt8.js";import{J as t,K as n,O as r,S as i,T as a,_ as o,a as s,b as c,c as l,d as u,f as d,g as f,n as p,o as m,s as h,t as g,u as _,y as v}from"./_plugin-vue_export-helper-BHs1AlSl.js";import{t as y}from"./index-VNE3eVQ_.js";var b={key:0,class:`post-detail`},x={class:`post-card`},S={class:`post-header`},C={class:`post-meta`},w={key:0,class:`author`},T={class:`type-badge`},E={class:`post-stats`},D={class:`stat`},O={class:`stat`},k={key:0,class:`stat`},A=[`href`],j={key:0,class:`selftext`},M={key:1,class:`trend`},N={class:`trend-meta`},P={class:`comments-title`},F={class:`comments`},I={key:0,class:`empty`},L={key:1,class:`loading`},R=d({name:`CommentThread`,props:{comment:Object,depth:{type:Number,default:0}},setup(e){function t(e){return e>=100?`#ff4500`:e>=10?`#ffd700`:`var(--text-muted)`}return{scoreColor:t,comment:e.comment,depth:e.depth}},template:`
    <div class="comment" :style="{ marginLeft: depth * 16 + 'px' }">
      <div class="comment-header">
        <span v-if="comment.author" class="comment-author">u/{{ comment.author }}</span>
        <span v-else class="comment-author deleted">[deleted]</span>
        <span class="comment-score" :style="{ color: scoreColor(comment.score) }">
          {{ comment.score }} ▲
        </span>
      </div>
      <div class="comment-body">{{ comment.body }}</div>
      <div v-if="comment.replies && comment.replies.length" class="comment-replies">
        <CommentThread
          v-for="reply in comment.replies.slice(0, 10)"
          :key="reply.id"
          :comment="reply"
          :depth="depth + 1"
        />
        <div v-if="comment.replies.length > 10" class="more-replies">
          +{{ comment.replies.length - 10 }} more replies
        </div>
      </div>
    </div>
  `}),z=g(d({components:{CommentThread:R},__name:`PostDetailView`,setup(d){let g=y(),z=a(null),B=a([]),V=a([]),H=a(!0);f(U);async function U(){let t=Number(g.params.id);z.value=await e.getPost(t),B.value=await e.getPostComments(t),V.value=await e.getPostSnapshots(t),H.value=!1}function W(){return z.value?`https://reddit.com${z.value.permalink}`:`#`}function G(){if(V.value.length<2)return null;let e=V.value[0],t=V.value[V.value.length-1];return{scoreDiff:t.score-e.score,commentDiff:t.num_comments-e.num_comments,count:V.value.length}}return(e,a)=>{let d=c(`router-link`);return!H.value&&z.value?(o(),l(`div`,b,[u(d,{to:`/posts`,class:`back`},{default:i(()=>[...a[0]||=[_(`← Back to posts`,-1)]]),_:1}),s(`div`,x,[s(`div`,S,[s(`h1`,null,t(z.value.title),1),s(`div`,C,[z.value.author?(o(),l(`span`,w,`u/`+t(z.value.author),1)):h(``,!0),s(`span`,null,`/r/`+t(z.value.subreddit?.name),1),s(`span`,T,t(z.value.post_type),1)]),s(`div`,E,[s(`span`,D,`▲ `+t(z.value.score),1),s(`span`,O,`💬 `+t(z.value.num_comments),1),z.value.upvote_ratio?(o(),l(`span`,k,`⚡ `+t((z.value.upvote_ratio*100).toFixed(0))+`%`,1)):h(``,!0),s(`a`,{href:W(),target:`_blank`,class:`stat link`},`Open on Reddit →`,8,A)])]),z.value.selftext?(o(),l(`div`,j,t(z.value.selftext),1)):h(``,!0),G()?(o(),l(`div`,M,[s(`span`,{class:n(G().scoreDiff>=0?`trend-up`:`trend-down`)},t(G().scoreDiff>=0?`↑`:`↓`)+` `+t(Math.abs(G().scoreDiff))+` score `,3),s(`span`,{class:n(G().commentDiff>=0?`trend-up`:`trend-down`)},t(G().commentDiff>=0?`↑`:`↓`)+` `+t(Math.abs(G().commentDiff))+` comments `,3),s(`span`,N,`(`+t(G().count)+` snapshots)`,1)])):h(``,!0)]),s(`h2`,P,`Comments (`+t(B.value.length)+` threads)`,1),s(`div`,F,[(o(!0),l(p,null,v(B.value,e=>(o(),m(r(R),{key:e.id,comment:e,depth:0},null,8,[`comment`]))),128))]),B.value.length===0?(o(),l(`div`,I,`No comments scraped yet.`)):h(``,!0)])):(o(),l(`div`,L,`Loading...`))}}}),[[`__scopeId`,`data-v-58949d38`]]);export{z as default};