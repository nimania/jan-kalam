# Persian source expansion registry

This file tracks Persian/Iran-focused sources that should be evaluated for ingestion.
Production feeds live in `scripts/seed.py`; entries stay here until an RSS/Atom/API
or a stable HTML adapter has been verified from the GitHub Actions environment.

## Already active
IRNA, ISNA, Mehr, Fars, KhabarOnline, Hamshahri Online, IRIB News, YJC, Tabnak,
Fararu, Entekhab, Asriran, Fardanews, Rouydad24, Aftab News, Mashregh, Ensaf News,
Payam-e Ma, Varzesh3, Digiato, BBC Persian, Iran International, DW Persian,
Euronews Persian, Kayhan London, Zeitoon, Zoomit, Gamefa, Salamat News,
Akhbar Rooz, Radio Zamaneh, Center for Human Rights in Iran.

## Candidate — feed/API or adapter still to verify
- Alef — https://alef.ir/
- Arya News — http://www.aryanews.com/
- Tehran Picture — http://www.tehranpicture.ir/
- ANA — http://www.ana.ir/
- Anadolu Persian — https://www.aa.com.tr/fa
- AvaToday — https://avatoday.net/fa
- Jomhouri — http://jomhouri.com/
- Eghtesad News — http://www.eghtesadnews.com/
- EcoIran — https://ecoiran.com/
- EcoNews — http://www.econews.ir/fa/
- Al Alam Persian — https://fa.alalam.ir/
- Al Arabiya Persian — http://farsi.alarabiya.net/
- Iran Prison Atlas — https://ipa.united4iran.org/fa/
- Etemad Online — https://etemadonline.com/
- Iran Online — http://www.ion.ir/
- Iran Briefing — https://irbr.news/
- Iranshahr News Agency — http://iranshahrnewsagency.com/
- IranWire Persian — https://iranwire.com/fa/
- ISCA News — http://iscanews.ir/
- ILNA — http://www.ilna.ir/
- Independent Persian — https://www.independentpersian.com/
- Tahlil Bazaar — https://www.tahlilbazaar.com/
- Baztab — https://baztab.ir/
- Bahar News — http://baharnews.ir/
- Parsine — http://parsine.com/
- Peyknet — https://www.pyknet.org/
- Tik — http://tik.ir/
- Tasnim — http://tasnimnews.com/
- Jamaran — http://jamaran.ir/
- Khordad News — http://khordadnews.ir/
- Iranian Diplomacy — http://www.irdiplomacy.ir/
- RFI Persian — http://fa.rfi.fr/
- Raja News — http://rajanews.com/
- Radio Farda — http://www.radiofarda.com/
- Roozno — http://www.roozno.com/
- Hengaw — https://hengaw.net/fa
- Salam Cinema — http://www.salamcinama.ir/
- Cinema Journal — http://www.cinemajournal.ir/
- CinemaPress — http://www.cinemapress.ir/
- Kurdistan Human Rights Network — http://kurdistanhumanrights.net/fa/
- FCNN — http://www.fcnn.com/
- Shafaqna Persian — http://fa.shafaqna.com/
- Asharq Al-Awsat Persian — https://persian.aawsat.com/
- VOA Persian — http://ir.voanews.com/
- Sputnik Persian — http://ir.sputniknews.com/
- Voice of Restart — https://voiceofrestart.com/persian/
- Faraz — https://www.faraz.ir/
- Caffe Cinema — http://caffecinema.com/
- Kurdane — http://www.kurdane.com/
- Gooya News — https://news.gooya.com/
- Gooya — http://gooya.com/
- Mohabat News — https://mohabatnews.com/
- Melli-Mazhabi — http://melimazhabi.com/
- Musicema — http://www.musicema.com/
- Mizan — https://www.mizan.news/
- RFI Observers Persian — http://observers.rfi.fr/fa/
- Nasim Online — http://nasimonline.ir/
- Tandorosti Mag — https://tandorostimag.com/
- Noandish — http://noandish.com/
- 90 Eghtesadi — https://www.90eghtesadi.com/
- IPNA / Varzesh Iran — http://ipna.ir/
- Honar Online — http://www.honaronline.ir/
- HRANA — http://hra-news.org/
- Iran Emrooz — http://www.iran-emrooz.net/
- Iran Press News — http://iranpressnews.com/
- Iran Global — http://www.iranglobal.info/
- Balatarin — http://balatarin.com/
- Jebhe Melli news — https://jebhe.net/
- Sarkhat — http://www.sarkhat.com/
- Shahre Khabar — http://www.shahrekhabar.com/
- Hambastegi Melli — http://hambastegimeli.com/

## Adapter priority
1. Gooya News
2. EcoIran / Eghtesad News
3. ANA / ILNA / Tasnim
4. Honar Online / Musicema / CinemaPress / Salam Cinema
5. HRANA / Hengaw / Kurdistan Human Rights Network
6. Independent Persian / IranWire / Radio Farda / VOA Persian

Do not guess RSS URLs. A candidate moves into production only after its endpoint returns
parseable, current items from the deployment environment.
