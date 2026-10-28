"""Public experimental time-series evidence, separate from the v12.2 decision engine.

No source value in this module overwrites production assumptions or clears gates.
"""
from pathlib import Path
import io
import json
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager
import pandas as pd

ROOT = Path(__file__).resolve().parent
DATA = ROOT / 'data/timeseries'
COLORS = {'Baseline':'#B77928','Fast':'#0A948C'}
LABELS = {'Baseline':'기준 화성','Fast':'고속 화성'}

def load_data(filename):
    return pd.read_csv(DATA / filename)

def setup_style():
    font = ROOT/'assets/fonts/NanumGothic.ttf'
    font_manager.fontManager.addfont(str(font))
    plt.rcParams.update({'font.family':font_manager.FontProperties(fname=str(font)).get_name(),
        'axes.unicode_minus':False, 'font.size':12, 'axes.titlesize':16, 'axes.labelsize':13,
        'axes.edgecolor':'#A8B7C3','axes.labelcolor':'#253746', 'text.color':'#132A3E',
        'xtick.color':'#627486','ytick.color':'#627486', 'axes.spines.top':False,
        'axes.spines.right':False,'grid.color':'#DFE7EB','figure.facecolor':'white',
        'savefig.facecolor':'white','svg.fonttype':'none'})

def _axis(ax):
    ax.grid(axis='y',alpha=.75)
    ax.set_axisbelow(True)

def plot_drying():
    setup_style();d=load_data('drying_nmp_digitized.csv');q=load_data('drying_quality_table5.csv')
    fig,axs=plt.subplots(1,2,figsize=(14.4,6.8),gridspec_kw={'width_ratios':[1.25,1]})
    fig.subplots_adjust(left=.07,right=.96,bottom=.23,top=.78,wspace=.30)
    fig.suptitle('건조 시계열: 후반 용매 제거와 품질을 함께 확인',x=.07,y=.96,ha='left',fontsize=22,fontweight='bold')
    fig.text(.07,.885,'NMC111 / NMP · 실험실 열풍건조 · 그림 추출 근사값 + 원문 표 수치',fontsize=12,color='#627486')
    ax=axs[0];ax.plot(d.time_s,d.nmp_kg_per_kg_dry,'o-',color='#367AC1',lw=2,ms=5)
    ax.set(xlabel='건조 경과 시간 (s)',ylabel='NMP 잔량 (kg NMP / kg 건조 전극)',xlim=(0,950),ylim=(0,2.3))
    ax.set_title('100°C, 1 m/s: 대표 건조 곡선',loc='left',pad=14)
    ax.annotate('후반 감률 구간\n시간 단축은 별도 검증',xy=(610,.22),xytext=(460,1.12),
        arrowprops={'arrowstyle':'->','color':'#627486'},fontsize=12,color='#627486')
    _axis(ax)
    ax=axs[1]
    ax.errorbar(q.rate_1e4_kg_m2_s,q.uncalendered_crack_pct,xerr=q.rate_sd,yerr=q.crack_sd,
        fmt='o',ms=7,color='#B77928',ecolor='#D5BA92',capsize=4)
    for _,r in q.iterrows():
        ax.annotate(f"{int(r.temperature_c)}°C / {r.air_speed_m_s:g} m/s",(r.rate_1e4_kg_m2_s,r.uncalendered_crack_pct),
            xytext=(5,10),textcoords='offset points',fontsize=10)
    ax.set(xlabel='정률 건조속도 (×10⁻⁴ kg NMP/m²/s)',ylabel='캘린더 전 표면 크랙 면적 (%)',xlim=(0,4.2),ylim=(0,13))
    ax.set_title('건조속도와 구조 변화: Table 5',loc='left',pad=14);_axis(ax)
    fig.text(.07,.115,'해석  65 wt%의 용매 감소만으로 1.2배 속도에서 잔류 NMP·접착·크랙을 보증할 수 없음',fontsize=13,color='#0A948C')
    fig.text(.07,.065,'출처: Bryntesen et al. (2023), Batteries 9, 96, p.9 Fig.4·Table 5. DOI: 10.3390/batteries9020096',fontsize=10,color='#627486')
    fig.text(.07,.025,'18개 점은 그림에서 추출한 근사값. 표 오차막대는 원문 ± 값. C사 60→65 wt%·NIR 비교시험이 아님.',fontsize=10,color='#627486')
    return fig

def plot_cycle(temperature=None,individual=False):
    setup_style();d=load_data('formation_cycle_capacity.csv')
    temps=[temperature] if temperature else ['RT','45C']
    fig,axes=plt.subplots(1,len(temps),figsize=(14.4,6.8),squeeze=False)
    fig.subplots_adjust(left=.07,right=.96,bottom=.23,top=.78,wspace=.22)
    fig.suptitle('화성 품질: 같은 셀의 후속 용량 유지율로 비교',x=.07,y=.96,ha='left',fontsize=22,fontweight='bold')
    fig.text(.07,.885,'NMC111/흑연 2.36 Ah 파우치 · 저자 공개 가공 데이터 · 39셀 공통 관측 5회',fontsize=12,color='#627486')
    for ax,temp in zip(axes[0],temps):
        part=d[d.aging_temperature==temp]
        for protocol,g in part.groupby('protocol',sort=True):
            s=g.groupby('cycle_index').retention_pct
            med=s.median();lo=s.quantile(.25);hi=s.quantile(.75)
            if individual:
                for _,c in g.groupby('cell_id'):ax.plot(c.cycle_index,c.retention_pct,color=COLORS[protocol],lw=.7,alpha=.18)
            ax.fill_between(med.index,lo,hi,color=COLORS[protocol],alpha=.13)
            ax.plot(med.index,med.values,'o-',color=COLORS[protocol],lw=2.5,ms=5,label=f'{LABELS[protocol]} (n={g.cell_id.nunique()})')
            ax.annotate(f'{med.iloc[-1]:.1f}%',(364,med.iloc[-1]),xytext=(6,0),textcoords='offset points',color=COLORS[protocol],fontsize=12)
        ax.axhline(80,color='#A8B7C3',ls='--',lw=1)
        ax.set(title='후속 사이클 시험: '+('실온 (RT)' if temp=='RT' else '45°C'),xlabel='후속 사이클 번호 (달력 시간이 아님)',ylabel='C/3 진단 용량 / 해당 셀 cycle 2 용량 (%)',xlim=(0,410),ylim=(65,103))
        ax.legend(loc='lower left',frameon=False,fontsize=11);_axis(ax)
    fig.text(.07,.115,'해석  이 셀 설계에서는 고속 화성군의 용량 유지가 양호함. C사의 20→16 h 검증은 별도 필요',fontsize=13,color='#0A948C')
    fig.text(.07,.065,'출처: Weng et al. (2021), Joule. DOI: 10.1016/j.joule.2021.09.015 · 저자 CSV(2022) C/3 RPT 필드',fontsize=10,color='#627486')
    fig.text(.07,.025,'실선: 군별 중앙값 / 음영: 25–75% 범위(신뢰구간 아님). 결측 보간 없이 공통 cycle 2·55·158·261·364만 사용.',fontsize=10,color='#627486')
    return fig

def plot_rest(individual=False):
    setup_style();d=load_data('formation_rest_voltage.csv')
    fig,axs=plt.subplots(1,2,figsize=(14.4,6.8),gridspec_kw={'width_ratios':[1.25,1]})
    fig.subplots_adjust(left=.07,right=.96,bottom=.23,top=.78,wspace=.30)
    fig.suptitle('화성 후 전압 변화: 관찰 시간과 채널 점유를 분리',x=.07,y=.96,ha='left',fontsize=22,fontweight='bold')
    fig.text(.07,.885,'실온 6 h 휴지 · 39셀 · 초기 전압 대비 하락량 · 미세단락 정답 라벨 없음',fontsize=12,color='#627486')
    for proto,g in d.groupby('protocol',sort=True):
        s=g.groupby('rest_time_h').voltage_drop_mv
        med=s.median();lo=s.quantile(.25);hi=s.quantile(.75)
        if individual:
            for _,c in g.groupby('cell_id'):axs[0].plot(c.rest_time_h,c.voltage_drop_mv,color=COLORS[proto],lw=.6,alpha=.2)
        axs[0].fill_between(med.index,lo,hi,color=COLORS[proto],alpha=.13)
        axs[0].plot(med.index,med,'o-',color=COLORS[proto],lw=2.5,ms=5,label=f'{LABELS[proto]} (n={g.cell_id.nunique()})')
        piv=g.pivot(index='cell_id',columns='rest_time_h',values='voltage_drop_mv')
        inc=piv.diff(axis=1).iloc[:,1:]
        vals=inc.median()
        axs[1].plot(vals.index,vals,'o-',color=COLORS[proto],lw=2.5,ms=5,label=LABELS[proto])
    ax=axs[0];ax.axvline(40/60,color='#7861B8',ls='--',lw=1.4)
    ax.text(.78,27,'40분: 팀의 추가 점유 예산',fontsize=10,color='#7861B8')
    ax.set(xlabel='휴지 경과 시간 (h)',ylabel='휴지 시작 대비 전압 하락량 (mV)',xlim=(0,6.3),ylim=(0,30))
    ax.set_title('1 h 간격으로 추출된 전압 변화',loc='left',pad=14)
    ax.legend(loc='lower right',frameon=False,fontsize=11);_axis(ax)
    ax=axs[1];ax.set_title('각 1 h 구간의 전압 하락량',loc='left',pad=14)
    ax.set(xlabel='관찰 구간 종료 시점 (h)',ylabel='직전 1 h 동안의 전압 하락량 (mV)',xlim=(.7,6.3),ylim=(0,15))
    ax.set_xticks([1,2,3,4,5,6]);ax.legend(frameon=False,fontsize=11);_axis(ax)
    fig.text(.07,.115,'해석  초기 전압 변화에는 완화가 섞임. 6 h 진단을 화성 채널에 추가하면 40분 예산을 초과',fontsize=13,color='#0A948C')
    fig.text(.07,.065,'출처: Weng et al. (2021), Joule. DOI: 10.1016/j.joule.2021.09.015 · 저자 CSV(2022) 6 h rest 필드',fontsize=10,color='#627486')
    fig.text(.07,.025,'중앙값·IQR 표시. 0 h는 정의한 기준점. 선은 관측점 연결이며 40분 값·불량 검출력·14일 단축을 추정하지 않음.',fontsize=10,color='#627486')
    return fig

def figure_bytes(fig,fmt='png'):
    b=io.BytesIO();fig.savefig(b,format=fmt,dpi=200);return b.getvalue()

def render_timeseries_panel():
    import streamlit as st
    st.markdown('### 공개 시계열로 보는 검증 포인트')
    st.caption('원출처 2개에서 시계열 3종을 재구성했습니다. C사 실측이 아니며 v12.2 결과나 품질 관문을 자동 변경하지 않습니다.')
    selection=st.selectbox('시계열 선택',['① 건조 중 NMP 잔량','② 화성 방식별 후속 용량','③ 화성 후 6시간 전압 변화'],key='ts_evidence_choice')
    show_cells=False
    if selection.startswith('①'):
        fig=plot_drying();filename='drying_nmp_digitized.csv';stem='01_drying'
        st.warning('근거 수준: 논문 그림의 18개 점을 추출한 근사값. NIR 절감률이나 60→65 wt% 건조시간의 실측값이 아닙니다.')
        st.write('**확인할 조건:** 1.2배 속도에서 출구 잔류 NMP·접착·크랙을 동시에 측정합니다. 속도별 전력(kWh/m²)을 별도로 기록해야 에너지 효과까지 검증할 수 있습니다.')
    elif selection.startswith('②'):
        temperature=st.selectbox('후속 시험 온도',['둘 다','실온 (RT)','45°C'],key='ts_temp')
        show_cells=st.checkbox('개별 셀 곡선 표시',key='ts_cycle_individual')
        fig=plot_cycle({'둘 다':None,'실온 (RT)':'RT','45°C':'45C'}[temperature],show_cells)
        filename='formation_cycle_capacity.csv';stem='02_formation_quality'
        st.info('저자 실험 데이터: NMC111/흑연 2.36 Ah 파우치, 39셀. 후속 사이클 번호를 실제 경과 일수로 환산하지 않습니다.')
        st.write('**확인할 조건:** C사 동일 셀·동일 시험조건 대조군으로 20 h와 16 h를 비교하고 수명·가스·저항을 검증합니다. 이 곡선만으로 C사 비열등 관문을 완료 처리할 수 없습니다.')
    else:
        show_cells=st.checkbox('개별 셀 곡선 표시',key='ts_rest_individual')
        fig=plot_rest(show_cells);filename='formation_rest_voltage.csv';stem='03_rest_voltage'
        st.warning('6 h 관찰 데이터에는 미세단락 정답 라벨이 없습니다. 조기 선별 검출력이나 14일 에이징 단축의 승인 근거로 사용할 수 없습니다.')
        st.write('**확인할 조건:** 문헌 14 h/56 h는 진단 단계 제외 시간입니다. 6 h 휴지를 같은 화성 채널에 추가할지, 별도 전압 측정기로 분리할지 정하고 추가 점유 ≤40분을 다시 확인합니다.')
    st.pyplot(fig,width='stretch')
    c1,c2=st.columns(2)
    c1.download_button('현재 그래프 PNG',figure_bytes(fig),file_name=stem+'.png',mime='image/png',key='ts_png_'+stem)
    c2.download_button('시계열 CSV',(DATA/filename).read_bytes(),file_name=filename,mime='text/csv',key='ts_csv_'+stem)
    plt.close(fig)
    with st.expander('출처·가공 방법·원자료 보기'):
        source=json.loads((DATA/'sources.json').read_text(encoding='utf-8'))['sources'][0 if selection.startswith('①') else 1]
        st.write(f"**{source['authors']} ({source['year']})** — {source['title']}")
        st.markdown(f"[논문 DOI]({source['url']})")
        if 'data_url' in source:st.markdown(f"[저자 공개 CSV]({source['data_url']})")
        st.write('원문 위치: '+source['locator']);st.write('처리 방법: '+source['processing'])
        st.dataframe(load_data(filename),hide_index=True,width='stretch')
    st.caption('이 자료로 아직 확인할 수 없는 조건: C사 고정부하 f, NIR 현장 절감률, 승인 슬롯 +13.68%, 결함 양성 299개 검출력. 모두 기존 상태를 유지합니다.')
    st.divider()

if __name__=='__main__':
    out=ROOT/'timeseries_outputs';out.mkdir(exist_ok=True)
    for stem,fun in [('01_drying',plot_drying),('02_formation_quality',plot_cycle),('03_rest_voltage',plot_rest)]:
        fig=fun()
        for fmt in ['png','svg']:(out/f'{stem}.{fmt}').write_bytes(figure_bytes(fig,fmt))
        plt.close(fig)
    print(out)
