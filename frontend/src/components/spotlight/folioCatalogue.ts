import survey from '@/assets/folio/survey.svg?no-inline';
import workshop from '@/assets/folio/workshop.svg?no-inline';
import field from '@/assets/folio/field.svg?no-inline';

function plate(sprite: string, id: string, title: string, reverse: string) {
  return {
    id,
    title,
    reverse,
    front: sprite + '#' + id + '-front',
    back: sprite + '#' + id + '-back',
  };
}
export const folios = [
  plate(survey, 'orrery', '浑天仪', '行星轨道'),
  plate(survey, 'telescope', '圆顶观星台', '星座测绘'),
  plate(survey, 'lighthouse', '海角灯塔', '菲涅耳透镜'),
  plate(survey, 'bathysphere', '深海潜水球', '深海生物'),
  plate(survey, 'balloon', '热气球', '高空气象航迹'),
  plate(survey, 'steam-locomotive', '蒸汽机车', '车轮与连杆'),
  plate(survey, 'bridge', '悬索桥', '受力桁架'),
  plate(workshop, 'gramophone', '留声机', '唱针与声槽'),
  plate(workshop, 'typewriter', '打字机', '字锤与铅字'),
  plate(workshop, 'camera', '蛇腹相机', '光圈与胶卷'),
  plate(workshop, 'press', '手动印刷机', '活字版盘'),
  plate(workshop, 'loom', '提花织机', '穿孔花卡'),
  plate(workshop, 'telegraph', '电报机', '线圈与纸带'),
  plate(workshop, 'chronometer', '航海钟', '擒纵机构'),
  plate(field, 'glasshouse', '玻璃温室', '蕨叶脉络'),
  plate(field, 'nautilus', '鹦鹉螺', '剖面螺室'),
  plate(field, 'moth', '飞蛾标本', '翅鳞微观图'),
  plate(field, 'volcano', '火山山脊', '地层剖面'),
  plate(field, 'windmill', '荷兰风车', '木齿轮磨盘'),
  plate(field, 'airship', '齐柏林飞艇', '艇身骨架'),
];

export function advancePlate(index: number, delta: number) {
  return (index + delta + folios.length) % folios.length;
}
