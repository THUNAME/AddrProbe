# AddrProbe
## An Internet-wide Active IPv6 Address Probing System with Limited Seeds
For a target prefix, AddrProbe initiates probing using address patterns derived from seeded prefixes with similar routing attributes. During probing, AddrProbe dynamically optimizes these patterns to approximate the true distribution of the target prefix, achieving high probing accuracy while supporting efficient probing of all Internet-wide routing prefixes with a small number of seeds.

## Getting Started

#### Clone the repo

```
git clone https://github.com/AddrProbe/AddrProbe.git
```


#### Create a virtual environment for Python3.8.10

```
conda create -n py38 python=3.8.10
conda activate py38
```

#### Install Zmap
#####  Building from Source

```
git clone https://github.com/tumi8/zmap.git
cd zmap
```
##### Installing ZMap Dependencies

On Debian-based systems (including Ubuntu):
```
sudo apt-get install build-essential cmake libgmp3-dev gengetopt libpcap-dev flex byacc libjson-c-dev pkg-config libunistring-dev
```

On RHEL- and Fedora-based systems (including CentOS):
```
sudo yum install cmake gmp-devel gengetopt libpcap-devel flex byacc json-c-devel libunistring-devel
```

On macOS systems (using Homebrew):
```
brew install pkg-config cmake gmp gengetopt json-c byacc libdnet libunistring
```

##### Building and Installing ZMap

```
cmake .
make -j4
sudo make install
```

#### Install  dependencies
```
conda activate py38
conda install numpy scipy scikit-learn matplotlib tqdm pandas 
conda install pytorch torchvision torchaudio pytorch-cuda=11.7 -c pytorch -c nvidia
conda install pytorch pytorch-cuda=11.7 -c pytorch -c nvidia
pip3 install pyasn
pip3 install setuptools
```

#### Run the code in the ./AddrProbe/code directory

```
cd AddrProbe/code
python3 data_pre.py
python3 main_train.py
cp -r ../result/result_template ../result/result
python3 main_test_seeded_prefix.py
mv ../result/result ../result/result_seeded_prefix
cp -r ../result/result_template ../result/result
python3 main_test_unseeded_prefix.py
python3 sat_aliased_prefix.py
```

If you want to change the default configuration, you can edit `DefaultConfig` in `AddrProbe/code/config.py`. Note that the first thing you need to do is to set the Zmap parameters in it, including the source IPv6 address and so on.


## Result
After running the programmings, you can get the output in the file directory that you set in the `AddrProbe/code/config.py`. For each prefix, you can get the newly probed active address.
* Probing results for seeded prefixes are in `AddrProbe/result/result_seeded_prefix/active_address_bank`
* Probing results for unseeded prefixes are in `AddrProbe/result/result_unseeded_prefix/active_address_bank`
* Probing aliased prefix for seeded prefixes are in `AddrProbe/result/result_seeded_prefix/zmap_result/aliased_prefix.txt`
* Probing aliased prefix for unseeded prefixes are in `AddrProbe/result/result_seeded_prefix/zmap_result/aliased_prefix.txt`


# Probing Results of AddrProbe 
We deployed AddrProbe on the Internet and conducted continuous iterative probes. Up to now, we have accumulated 562 million active addresses, which covers 189,738 routing prefixes and 29,066 ASes, accounting for 90% and 89% of the routing prefixes announced by the BGP system and ASes, respectively. In addition, we have detected 23,196 aliased prefixes, covering about $\text{1.2}\times\text{10}^{\text{33}}$ aliased addresses. The above data can be obtained and used solely for academic research.

## Data Open Source Notice

### Usage Restrictions
This data is only allowed to be used for academic research. Any form of commercial use, data resale, or other non-academic use is strictly prohibited. Without permission, the data shall not be used to develop commercial products, conduct profit-making analysis, or disseminate it to commercial institutions.

### Acquisition Method
If you need to obtain the data, please send an email to [cdg22@mails.tsinghua.edu.cn] using your academic institution email. The email subject should indicate: [Data Name] (Active Addresses or Aliased Prefixes) Application for Academic Use - [Applicant's Name] - [Affiliated Institution]. The content of the email should include the following information:
* Applicant's name, affiliated academic institution, and title/identity (such as graduate student, researcher, etc.).
* Specific research project name, research purpose, and brief content for which the data is planned to be used.
* The required data scale, including the quantity, scope and specific types of data needed.
* A commitment to using the data solely for academic research and not for commercial use or illegal dissemination.
  
### Review Process
We will review the email within 7 working days after receiving it. After the review is passed, we will send you the data acquisition link and usage authorization instructions via email. If the application is not approved, the specific reason will also be informed.

### Liability Statement
Since these data are sensitive to some of the probed networks, if it is found that the data user violates the agreement of academic use, we have the right to terminate the data usage authorization immediately and reserve the right to pursue legal liability. The data user shall bear all relevant responsibilities arising from the use of the data, and our side shall not be responsible for any problems that may occur during the data usage process.


We are committed to promoting academic cooperation and knowledge progress. Thank you for your understanding and cooperation! If you have any questions, please feel free to contact us at [cdg22@mails.tsinghua.edu.cn].
