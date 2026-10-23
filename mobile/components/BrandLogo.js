import React from 'react';
import { Text, View } from 'react-native';
import Svg, { Path } from 'react-native-svg';
import { BRAND } from '../src/brand-palette.mjs';
import { BRAND_MARK_PATHS } from '../src/logo-geometry.mjs';

/** One accessible brand lockup for Web and native. User-selected UI theme does
 * not recolour this mark. Accepts physical point sizes, not viewport scaling. */
export default function BrandLogo({
  markSize=35, textSize=23, variant='horizontal', inverse=false, tagline=false, style,
}) {
  const p=BRAND_MARK_PATHS;
  const slate=inverse?BRAND.paper:BRAND.slate;
  const mineral=inverse?'#D6E0E8':BRAND.mineral;
  const orientation=variant==='vertical'?'column':'row';
  const mark=<Svg width={markSize} height={markSize*120/116} viewBox="0 0 116 120" accessible={false}>
    <Path d={p.left} fill={slate}/>
    <Path d={p.centreDark} fill={slate}/>
    <Path d={p.centreLight} fill={mineral}/>
    <Path d={p.right} fill={slate}/>
    <Path d={p.decision} fill={BRAND.copper}/>
  </Svg>;
  if(variant==='mark') return <View accessible accessibilityLabel="ObraSignal" style={style}>{mark}</View>;
  const words=<Text allowFontScaling numberOfLines={1} style={{fontSize:textSize,fontWeight:'800',letterSpacing:-0.8,color:slate}}>
    Obra<Text style={{color:mineral}}>Signal</Text>
  </Text>;
  return <View accessible accessibilityLabel="ObraSignal" style={[{flexDirection:orientation,alignItems:'center',gap:variant==='vertical'?6:Math.max(7,markSize*.16)},style]}>
    {mark}
    <View style={{alignItems:variant==='vertical'?'center':'flex-start'}}>
      {words}
      {tagline?<Text style={{fontSize:Math.max(7,textSize*.33),letterSpacing:1.25,color:mineral,marginTop:2}}>CONTRATAÇÃO PÚBLICA INTELIGENTE</Text>:null}
    </View>
  </View>;
}
