import pandas as pd

def prepare_df(
            df,
            mapper,
            replicate_mapper,
            decoy_flag,
            species_dict,
            contaminant_flag,
            min_count_multispec
        ):
    df.rename(columns=mapper,inplace=True)

    replicate_to_raw = {}
    for k,v in replicate_mapper.items():
        try:
            replicate_to_raw[v].append(k) 
        except KeyError:
            replicate_to_raw[v] = [k]

    df = df[df["Reverse"] != decoy_flag]

    df["contaminant"] = df["Proteins"].str.contains(contaminant_flag)
    for species,flag in species_dict.items():
        df[species] = df["Proteins"].str.contains(flag)
    df["MULTI_SPEC"] = (df[list(species_dict.keys())].sum(axis=1) > min_count_multispec)
    df["replicate"] = df["Raw file"].map(replicate_mapper)

    df = pd.concat([df,pd.get_dummies(df["Raw file"])],axis=1)

    df = df[df["MULTI_SPEC"] == False]

    df.loc[df.index,"peptidoform"] = df.loc[df.index,"Modified sequence"]+df.loc[df.index,"Charge"].astype(str)
    count_non_zero = (df.groupby(["peptidoform","Raw file"]).sum()["Intensity"] > 0.0).groupby(level=[0]).sum() == 6
    allowed_peptidoforms = list(count_non_zero.index[count_non_zero])
    filtered_df = df[df["peptidoform"].isin(allowed_peptidoforms)]

    return filtered_df, replicate_to_raw