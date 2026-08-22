"""Evaluate ALINEA-style feedback metering under the Step 6 shared protocol."""
from __future__ import annotations
import argparse, csv, importlib.util, sys
from pathlib import Path
from statistics import mean

ROOT=Path(__file__).resolve().parents[3]; STEP_DIR=Path(__file__).resolve().parent; BASE_DIR=ROOT/"experiments/highway_merge_v3/step06_ramp_metering"
for path in (ROOT,ROOT/"src",STEP_DIR):
    if str(path) not in sys.path: sys.path.insert(0,str(path))
from controller import AlineaMeter
from experiments.common import write_metadata, write_rows
from traffic_merge_sim.demand import allocate_demand
from traffic_merge_sim.metrics import summarize_step_series, summarize_tripinfo
from traffic_merge_sim.network_config import HIGHWAY_MERGE_V3
from traffic_merge_sim.paths import GENERATED_OUTPUT_DIR
from traffic_merge_sim.route_builder import build_case_route_file
from traffic_merge_sim.sumo_runner import locate_sumo_binary

sys.modules.pop("controller",None); spec=importlib.util.spec_from_file_location("step604_base",BASE_DIR/"run.py"); assert spec and spec.loader; base=importlib.util.module_from_spec(spec); sys.modules[spec.name]=base; spec.loader.exec_module(base)
TOTAL,RATIO,SEEDS,DT=3950,"1:2",[7,42,99,123,2026],.25; STRATEGIES=["uncontrolled","cooperative_limited","ramp_fixed_1_5s","ramp_alinea"]
RAW=[*base.RAW_FIELDS,"alinea_rate_updates","alinea_mean_rate_veh_h"]

def alinea_case(main:int,ramp:int,seed:int,fcd:Path|None)->dict[str,object]:
    import traci
    out=GENERATED_OUTPUT_DIR/HIGHWAY_MERGE_V3.name; out.mkdir(parents=True,exist_ok=True); prefix=f"v3_step06_04_alinea_main_{main}_ramp_{ramp}_seed_{seed}"; route,trip,summary=(out/f"{prefix}{x}" for x in (".rou.xml",".tripinfo.xml",".summary.xml"))
    for p in (route,trip,summary,fcd):
        if p: p.unlink(missing_ok=True)
    if fcd: fcd.parent.mkdir(parents=True,exist_ok=True)
    build_case_route_file(route,main,ramp,1800,network=HIGHWAY_MERGE_V3); cmd=[locate_sumo_binary(),"-n",str(HIGHWAY_MERGE_V3.network_path),"-r",str(route),"--no-step-log","--quit-on-end","--tripinfo-output",str(trip),"--summary-output",str(summary),"--step-length",str(DT),"--xml-validation","never","--time-to-teleport","-1","--end","2400","--seed",str(seed)]
    if fcd: cmd += ["--fcd-output",str(fcd)]
    rec,meter,stopped=base.CompleteTTSMetrics(),AlineaMeter(),set(); traci.start(cmd)
    try:
        while traci.simulation.getTime()<2400:
            traci.simulationStep(); now=float(traci.simulation.getTime()); ids=set(traci.vehicle.getIDList()); rec.observe({v:float(traci.vehicle.getSpeed(v)) for v in ids},set(traci.simulation.getPendingVehicles()),set(traci.simulation.getLoadedIDList()),set(traci.simulation.getDepartedIDList()),set(traci.simulation.getArrivedIDList()),within_demand=now<=1800,step_length_s=DT)
            pos={v:float(traci.vehicle.getLanePosition(v)) for v in traci.edge.getLastStepVehicleIDs("ramp_upstream")}; held,released=meter.update(now,len(traci.lane.getLastStepVehicleIDs("main_merge_1")),pos,{v for v,p in pos.items() if p>=398})
            for v in (held & {v for v,p in pos.items() if p>=398})-stopped: traci.vehicle.setSpeed(v,0); stopped.add(v)
            for v in released & stopped & ids: traci.vehicle.setSpeed(v,-1); stopped.remove(v)
    finally: traci.close()
    result=rec.result(); steps=summarize_step_series(summary,1800); result.update(summarize_tripinfo(trip,int(result["accounted_loaded_veh"])),**steps); result.update(strategy="ramp_alinea",main_veh_h=main,ramp_veh_h=ramp,seed=seed,meter_release_interval_s=0,meter_releases=meter.releases,alinea_rate_updates=meter.rate_updates,alinea_mean_rate_veh_h=mean(meter.rate_history),unfinished_vehicles=max(0,int(steps["loaded_vehicles"])-int(result["arrived_veh"])),throughput=int(result["arrived_veh"])/1800,interventions=0); return result

def run(output_dir:Path|None=None,fcd_dir:Path|None=None)->Path:
    main,ramp=allocate_demand(TOTAL,RATIO); fcd_dir=fcd_dir or GENERATED_OUTPUT_DIR/"trajectories/v3-step06-04"; rows=[]
    for strategy in STRATEGIES:
        for seed in SEEDS:
            fcd=fcd_dir/f"ramp_alinea_main_{main}_ramp_{ramp}_seed_{seed}.fcd.xml" if strategy=="ramp_alinea" and seed==SEEDS[0] else None
            row=alinea_case(main,ramp,seed,fcd) if strategy=="ramp_alinea" else (base.run_metered_case(strategy,main,ramp,1800,600,seed,None,DT) if strategy=="ramp_fixed_1_5s" else base.STEP05_RUN.run_case(strategy,main,ramp,1800,600,seed,None,DT))
            row.update(total_demand_veh_h=TOTAL,demand_ratio=RATIO); row.setdefault("alinea_rate_updates",0); row.setdefault("alinea_mean_rate_veh_h",0); rows.append(row)
    results=output_dir or STEP_DIR/"results"; raw=write_rows(results/"alinea_raw.csv",[{field:row.get(field,0) for field in RAW} for row in rows],RAW); write_rows(results/"paired_confidence_summary.csv",base.paired_summary(rows),base.PAIRED_FIELDS); write_metadata(results/"metadata.json",{"experiment_id":"highway_merge_v3_step06_04_alinea","step_length_s":DT,"strategies":STRATEGIES,"seeds":SEEDS,"fcd_representative_only":True}); return raw
if __name__=="__main__":
    parser=argparse.ArgumentParser(); parser.add_argument("--output-dir",type=Path); parser.add_argument("--fcd-output-dir",type=Path); args=parser.parse_args(); print(run(args.output_dir,args.fcd_output_dir))
