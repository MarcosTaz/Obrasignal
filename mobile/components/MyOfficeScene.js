import React, {useState} from 'react';
import {View, Text, Pressable, Image, StyleSheet} from 'react-native';
import {CHAMPAGNE_WINDOWS, APPROVED_SCENE_SIZE} from '../src/my-office-geometry.mjs';
import {MODULES, routeFor, translate} from '../src/my-office-contract.mjs';

/**
 * Exact V23 scene viewer. Source image must be the approved 1672x941 original,
 * explicitly supplied by the integration layer; it is never replaced by an AI image.
 * Renders real native-web pressable hotspots. Unimplemented modules stay disabled.
 */
export default function MyOfficeScene({sceneSource, onNavigate, locale='pt'}) {
  const [width,setWidth]=useState(0);
  const [focused,setFocused]=useState(null);
  const height=width*APPROVED_SCENE_SIZE.height/APPROVED_SCENE_SIZE.width;
  if(!sceneSource) return <View accessible accessibilityLabel="Imagem aprovada ainda não instalada" style={styles.unavailable}><Text style={styles.info}>Cenário Champanhe original ainda não importado. Radar e Perfil permanecem disponíveis na navegação normal.</Text></View>;
  return <View style={styles.wrap}>
    <View onLayout={e=>setWidth(e.nativeEvent.layout.width)} style={styles.scene}>
      <Image source={sceneSource} resizeMode="contain" style={{width:'100%',aspectRatio:1672/941}} accessibilityLabel="My Office — arquitetura Champanhe aprovada"/>
      {width>0 && CHAMPAGNE_WINDOWS.map((quad,index)=>{
        const xs=quad.map(p=>p[0]),ys=quad.map(p=>p[1]);
        const x=Math.min(...xs)/1672*width,y=Math.min(...ys)/941*height;
        const w=(Math.max(...xs)-Math.min(...xs))/1672*width,h=(Math.max(...ys)-Math.min(...ys))/941*height;
        const module=MODULES[index],target=routeFor(module.id);
        const left=Math.min(...xs),top=Math.min(...ys),spanX=Math.max(...xs)-left,spanY=Math.max(...ys)-top;
        const polygon=quad.map(([px,py])=>`${((px-left)/spanX*100).toFixed(4)}% ${((py-top)/spanY*100).toFixed(4)}%`).join(', ');
        return <Pressable key={module.id}
          testID={'my-office-'+module.id}
          accessibilityRole="button"
          accessibilityLabel={translate(locale,module.id)}
          accessibilityState={{disabled:!target}}
          disabled={!target}
          onPress={()=>{setFocused(index);if(target&&onNavigate)onNavigate(target);}}
          onHoverIn={()=>setFocused(index)}
          onHoverOut={()=>setFocused(value=>value===index?null:value)}
          style={[styles.hotspot,{left:x,top:y,width:w,height:h,clipPath:`polygon(${polygon})`},focused===index&&styles.active]}
        ><Text style={styles.hotspotLabel}>{translate(locale,module.id)}{!target?' · indisponível':''}</Text></Pressable>;
      })}
    </View>
    <Text style={styles.note}>Cena original Champanhe · navegação real apenas nas áreas ligadas ao produto · sem dados demonstrativos</Text>
  </View>;
}
const styles=StyleSheet.create({
  wrap:{width:'100%',alignSelf:'stretch'},
  scene:{width:'100%',position:'relative',overflow:'hidden',backgroundColor:'#080C14'},
  unavailable:{padding:24,borderWidth:1,borderColor:'#876B44',borderRadius:10,backgroundColor:'#111822'},
  info:{color:'#E2D4BE',fontSize:14},
  hotspot:{position:'absolute',borderWidth:1,borderColor:'rgba(255,217,147,0.4)',justifyContent:'center',alignItems:'center',backgroundColor:'rgba(7,13,26,0.11)'},
  active:{borderColor:'#FFDFA1',borderWidth:2,backgroundColor:'rgba(12,18,31,0.45)'},
  hotspotLabel:{fontSize:12,color:'#FFF1D7',fontWeight:'600',textAlign:'center',padding:4,textShadowColor:'#070707',textShadowRadius:4},
  note:{color:'#AFA18D',fontSize:12,marginTop:10}
});
