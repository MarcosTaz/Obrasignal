import React, {useEffect, useRef, useState} from 'react';
import {AccessibilityInfo, Animated, Easing, Pressable, StyleSheet, Text, useWindowDimensions, View} from 'react-native';
import Svg, {Circle, Defs, Line, LinearGradient, Path, RadialGradient, Rect, Stop} from 'react-native-svg';
import BrandLogo from './BrandLogo';
import {FONT_DISPLAY, FONT_BODY} from '../src/typography.mjs';

// Purposefully abstract intelligence scan. Never represents a real tender or live geolocation.
const COLORS={night:'#04101B',deep:'#081C2D',steel:'#78BEFB',copper:'#C87D55',soft:'#D8EAF6',line:'#2B5773'};
const DURATION=6200;
export default function WebIntro({onComplete}) {
  const {width,height}=useWindowDimensions();
  const small=width<600;
  const diameter=Math.max(225,Math.min(width*(small?.78:.55),height*.59,570));
  const timeline=useRef(new Animated.Value(0)).current;
  const [reduceMotion,setReduceMotion]=useState(false);
  useEffect(()=>{
    let active=true;
    AccessibilityInfo.isReduceMotionEnabled().then(v=>{if(active&&v)setReduceMotion(true)}).catch(()=>{});
    return ()=>{active=false};
  },[]);
  useEffect(()=>{
    if(reduceMotion){onComplete?.();return undefined}
    let called=false;
    const finish=()=>{if(!called){called=true;onComplete?.()}};
    const animation=Animated.timing(timeline,{toValue:1,duration:DURATION,easing:Easing.linear,useNativeDriver:true});
    const watchdog=setTimeout(finish,DURATION+1200);
    animation.start(({finished})=>{if(finished)finish()});
    return ()=>{clearTimeout(watchdog);animation.stop()};
  },[timeline,onComplete,reduceMotion]);
  const sweep=timeline.interpolate({inputRange:[0,1],outputRange:['-105deg','675deg']});
  const radarOpacity=timeline.interpolate({inputRange:[0,.05,.48,.67,.81,1],outputRange:[0,1,1,1,0,0]});
  const targetOpacity=timeline.interpolate({inputRange:[0,.40,.50,.61,.70,1],outputRange:[0,0,1,1,0,0]});
  const targetScale=timeline.interpolate({inputRange:[0,.41,.48,.56,.61,1],outputRange:[.65,.65,1.26,1,1,1]});
  const brandOpacity=timeline.interpolate({inputRange:[0,.61,.72,.83,1],outputRange:[0,0,.15,1,1]});
  const brandScale=timeline.interpolate({inputRange:[0,.61,.82,1],outputRange:[.92,.92,1,1]});
  const scanCaptionOpacity=timeline.interpolate({inputRange:[0,.07,.40,.54,1],outputRange:[0,1,1,0,0]});
  const foundCaptionOpacity=timeline.interpolate({inputRange:[0,.47,.54,.64,.72,1],outputRange:[0,0,1,1,0,0]});
  return <View style={s.root} accessibilityLabel="ObraSignal introduction — scanning, signal found, brand reveal" accessibilityRole="summary">
    <View pointerEvents="none" style={s.backdrop}>
      <Svg width="100%" height="100%" viewBox="0 0 1440 900" preserveAspectRatio="xMidYMid slice">
        <Defs><RadialGradient id="atmos"><Stop offset="0" stopColor="#20516A" stopOpacity=".38"/><Stop offset="1" stopColor="#04101B" stopOpacity="0"/></RadialGradient>
        <LinearGradient id="horizon" x1="0" y1="0" x2="1" y2="0"><Stop offset="0" stopColor="#071526"/><Stop offset=".55" stopColor="#17374B"/><Stop offset="1" stopColor="#06101B"/></LinearGradient></Defs>
        <Rect width="1440" height="900" fill={COLORS.night}/>
        <Circle cx="720" cy="452" r="620" fill="url(#atmos)"/>
        <Rect x="0" y="770" width="1440" height="130" fill="url(#horizon)" opacity=".65"/>
        {Array.from({length:19},(_,i)=><Line key={'v'+i} x1={i*80} y1="0" x2={i*80} y2="900" stroke={COLORS.steel} strokeOpacity=".07" strokeWidth=".8"/>)}
        {Array.from({length:12},(_,i)=><Line key={'h'+i} x1="0" y1={i*80} x2="1440" y2={i*80} stroke={COLORS.steel} strokeOpacity=".06" strokeWidth=".8"/>)}
      </Svg>
    </View>
    <View style={s.top}><Text style={s.eyebrow}>OBRASIGNAL / PROCUREMENT INTELLIGENCE</Text><Text style={s.topRight}>SYSTEM INTRODUCTION</Text></View>
    <View style={s.central}>
      <Animated.View pointerEvents="none" style={[s.radar,{width:diameter,height:diameter,opacity:radarOpacity}]}>
        <Svg width="100%" height="100%" viewBox="0 0 520 520">
          <Defs>
            <RadialGradient id="scanBase"><Stop offset="0" stopColor="#225574" stopOpacity=".32"/><Stop offset="1" stopColor="#071625" stopOpacity=".02"/></RadialGradient>
          </Defs>
          <Circle cx="260" cy="260" r="247" fill="url(#scanBase)" stroke="#4A8AAD" strokeOpacity=".66" strokeWidth="1.8"/>
          {[60,120,182].map(r=><Circle key={r} cx="260" cy="260" r={r} fill="none" stroke="#6AA8C8" strokeOpacity=".36" strokeWidth="1.1"/>)}
          <Line x1="260" y1="4" x2="260" y2="516" stroke="#82B7CE" strokeOpacity=".28"/>
          <Line x1="4" y1="260" x2="516" y2="260" stroke="#82B7CE" strokeOpacity=".28"/>
          <Path d="M79 79 L441 441 M441 79 L79 441" stroke="#6093AD" strokeOpacity=".14"/>
          <Circle cx="260" cy="260" r="8" fill="#C87D55"/>
          {Array.from({length:48},(_,i)=>{const a=i*Math.PI/24,outer=248,inner=i%4===0?235:243;return <Line key={'t'+i} x1={260+inner*Math.cos(a)} y1={260+inner*Math.sin(a)} x2={260+outer*Math.cos(a)} y2={260+outer*Math.sin(a)} stroke={i%4===0?'#C87D55':'#74C1EC'} strokeOpacity={i%4===0?.95:.46} strokeWidth={i%4===0?2:1}/>})}
        </Svg>
        <Animated.View style={[s.sweep,{transform:[{rotate:sweep}]}]}>
          <Svg width="100%" height="100%" viewBox="0 0 520 520">
            <Defs><LinearGradient id="beam" x1="0" y1="0" x2="1" y2="0"><Stop offset="0" stopColor="#6ECAF4" stopOpacity=".04"/><Stop offset="1" stopColor="#6ECAF4" stopOpacity=".34"/></LinearGradient></Defs>
            <Path d="M260 260 L130 49 A242 242 0 0 1 390 49 Z" fill="url(#beam)"/>
            <Line x1="260" y1="260" x2="389" y2="50" stroke="#91DDFF" strokeOpacity=".95" strokeWidth="2.6"/>
          </Svg>
        </Animated.View>
        <Animated.View style={[s.target,{left:'69%',top:'27%',opacity:targetOpacity,transform:[{scale:targetScale}]}]}>
          <Svg width="90" height="110" viewBox="0 0 90 110">
            <Circle cx="45" cy="38" r="35" fill="none" stroke={COLORS.copper} strokeWidth="1.5" strokeDasharray="5 5" opacity=".9"/>
            <Path d="M45 12 C29 12 18 24 18 40 C18 60 45 88 45 88 C45 88 72 60 72 40 C72 24 61 12 45 12Z" fill={COLORS.copper}/>
            <Circle cx="45" cy="39" r="10" fill="#082031"/>
          </Svg>
        </Animated.View>
      </Animated.View>
      <Animated.View pointerEvents="none" style={[s.brand,{opacity:brandOpacity,transform:[{scale:brandScale}]}]}>
        <BrandLogo variant={small?'vertical':'horizontal'} inverse markSize={small?105:150} textSize={small?43:67}/>
        <View style={s.brandRule}/><Text style={s.brandTag}>GLOBAL PROCUREMENT INTELLIGENCE</Text>
      </Animated.View>
      <View style={[s.caption,small&&{bottom:-55}]}>
        <Animated.Text style={[s.captionText,{opacity:scanCaptionOpacity}]}>SCANNING PUBLIC PROCUREMENT SIGNALS</Animated.Text>
        <Animated.Text style={[s.captionFound,{opacity:foundCaptionOpacity}]}>SIGNAL FOUND  /  OPPORTUNITY IDENTIFIED</Animated.Text>
      </View>
    </View>
    <View style={s.bottom}><Text style={s.bottomText}>DISCOVER · EVALUATE · ACT</Text><Pressable accessibilityRole="button" accessibilityLabel="Skip introduction" onPress={onComplete} style={s.skip}><Text style={s.skipText}>SKIP INTRO  →</Text></Pressable></View>
  </View>;
}
const s=StyleSheet.create({
 root:{position:'absolute',top:0,left:0,right:0,bottom:0,zIndex:9999,backgroundColor:COLORS.night,justifyContent:'space-between',alignItems:'center',paddingHorizontal:22,paddingVertical:27,overflow:'hidden'},
 backdrop:{position:'absolute',top:0,left:0,right:0,bottom:0},
 top:{width:'100%',maxWidth:1650,flexDirection:'row',alignItems:'center',justifyContent:'space-between',flexWrap:'wrap',gap:8},
 eyebrow:{color:COLORS.soft,fontFamily:FONT_BODY,fontSize:10,fontWeight:'800',letterSpacing:1.7},
 topRight:{color:'#7194AC',fontFamily:FONT_BODY,fontSize:10,letterSpacing:1.5},
 central:{flex:1,alignItems:'center',justifyContent:'center',width:'100%',minHeight:0},
 radar:{alignItems:'center',justifyContent:'center'},
 sweep:{position:'absolute',top:0,left:0,right:0,bottom:0},
 target:{position:'absolute',alignItems:'center',justifyContent:'center',marginLeft:-45,marginTop:-55},
 brand:{position:'absolute',alignItems:'center',justifyContent:'center',width:'100%',paddingHorizontal:10},
 brandRule:{height:2,width:83,backgroundColor:COLORS.copper,marginTop:22},
 brandTag:{color:'#BFD8E8',fontFamily:FONT_DISPLAY,fontSize:11,letterSpacing:2.3,fontWeight:'700',marginTop:16,textAlign:'center'},
 caption:{position:'absolute',bottom:8,alignItems:'center',justifyContent:'center',width:'100%',minHeight:34},
 captionText:{color:COLORS.soft,fontFamily:FONT_BODY,letterSpacing:2,fontSize:10,fontWeight:'800',textAlign:'center'},
 captionFound:{color:'#E7A87D',fontFamily:FONT_BODY,letterSpacing:1.7,fontSize:10,fontWeight:'800',position:'absolute',textAlign:'center'},
 bottom:{width:'100%',maxWidth:1650,flexDirection:'row',justifyContent:'space-between',alignItems:'center',gap:12},
 bottomText:{color:'#759DBA',fontFamily:FONT_BODY,fontSize:10,letterSpacing:1.7,fontWeight:'700'},
 skip:{paddingHorizontal:13,paddingVertical:10,minHeight:40,justifyContent:'center'},
 skipText:{fontFamily:FONT_BODY,color:'#C7DEED',fontWeight:'800',fontSize:11,letterSpacing:1.1}
});
