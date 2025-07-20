import 'dart:io';
import 'package:flutter/material.dart';
import 'package:google_mobile_ads/google_mobile_ads.dart';
import 'package:path_provider/path_provider.dart';
import 'package:permission_handler/permission_handler.dart';
import 'package:gallery_saver/gallery_saver.dart';

class StatusHomePage extends StatefulWidget {
  @override
  _StatusHomePageState createState() => _StatusHomePageState();
}

class _StatusHomePageState extends State<StatusHomePage> with SingleTickerProviderStateMixin {
  late TabController _tabController;
  late BannerAd _bannerAd;
  InterstitialAd? _interstitialAd;
  int _downloadCount = 0;
  int _lastTabIndex = 0;

  @override
  void initState() {
    super.initState();
    _tabController = TabController(length: 3, vsync: this);
    _tabController.addListener(_handleTabChange);
    _loadBannerAd();
    _loadInterstitialAd();
    _requestPermission();
  }

  Future<void> _requestPermission() async {
    await Permission.storage.request();
  }

  void _handleTabChange() {
    if (_tabController.index != _lastTabIndex) {
      _showInterstitialAd();
      _lastTabIndex = _tabController.index;
    }
  }

  void _loadBannerAd() {
    _bannerAd = BannerAd(
      adUnitId: 'ca-app-pub-4724124049234023/1673590966',
      size: AdSize.banner,
      request: AdRequest(),
      listener: BannerAdListener(),
    )..load();
  }

  void _loadInterstitialAd() {
    InterstitialAd.load(
      adUnitId: 'ca-app-pub-4724124049234023/6598614581',
      request: AdRequest(),
      adLoadCallback: InterstitialAdLoadCallback(
        onAdLoaded: (ad) => _interstitialAd = ad,
        onAdFailedToLoad: (error) => _interstitialAd = null,
      ),
    );
  }

  void _showInterstitialAd() {
    if (_interstitialAd != null) {
      _interstitialAd!.show();
      _loadInterstitialAd();
    }
  }

  void _onDownload() {
    _downloadCount++;
    if (_downloadCount % 2 == 0) {
      _showInterstitialAd();
    }
  }

  @override
  void dispose() {
    _tabController.dispose();
    _bannerAd.dispose();
    _interstitialAd?.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: Text('Status Downloader'),
        bottom: TabBar(
          controller: _tabController,
          tabs: [
            Tab(text: 'Images'),
            Tab(text: 'Videos'),
            Tab(text: 'Saved'),
          ],
        ),
      ),
      body: Column(
        children: [
          Expanded(
            child: TabBarView(
              controller: _tabController,
              children: [
                StatusGridView(type: 'image', onDownload: _onDownload),
                StatusGridView(type: 'video', onDownload: _onDownload),
                SavedGridView(),
              ],
            ),
          ),
          Container(
            height: 50,
            child: AdWidget(ad: _bannerAd),
          ),
        ],
      ),
    );
  }
}

class StatusGridView extends StatefulWidget {
  final String type;
  final VoidCallback onDownload;
  const StatusGridView({required this.type, required this.onDownload});

  @override
  _StatusGridViewState createState() => _StatusGridViewState();
}

class _StatusGridViewState extends State<StatusGridView> {
  List<FileSystemEntity> statuses = [];

  @override
  void initState() {
    super.initState();
    _loadStatuses();
  }

  Future<void> _loadStatuses() async {
    final Directory? dir = Directory('/storage/emulated/0/WhatsApp/Media/.Statuses');
    if (await dir.exists()) {
      final files = dir.listSync().where((f) {
        final name = f.path;
        return widget.type == 'image' ? name.endsWith('.jpg') : name.endsWith('.mp4');
      }).toList();
      setState(() => statuses = files);
    }
  }

  Future<void> _saveStatus(FileSystemEntity file) async {
    final savedDir = Directory('/storage/emulated/0/StatusSaver');
    if (!await savedDir.exists()) await savedDir.create();
    final fileName = file.path.split('/').last;
    final newPath = '${savedDir.path}/$fileName';
    await File(file.path).copy(newPath);
    widget.onDownload();
    await GallerySaver.saveImage(newPath);
    ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('Saved to gallery')));
  }

  @override
  Widget build(BuildContext context) {
    return statuses.isEmpty
        ? Center(child: Text('No ${widget.type} statuses found'))
        : GridView.builder(
            padding: EdgeInsets.all(10),
            gridDelegate: SliverGridDelegateWithFixedCrossAxisCount(
              crossAxisCount: 3,
              crossAxisSpacing: 5,
              mainAxisSpacing: 5,
            ),
            itemCount: statuses.length,
            itemBuilder: (context, index) {
              final file = statuses[index];
              return GestureDetector(
                onTap: () => _saveStatus(file),
                child: Stack(
                  fit: StackFit.expand,
                  children: [
                    Image.file(
                      File(file.path),
                      fit: BoxFit.cover,
                    ),
                    if (widget.type == 'video')
                      Align(
                        alignment: Alignment.center,
                        child: Icon(Icons.play_circle, color: Colors.white70, size: 30),
                      ),
                  ],
                ),
              );
            },
          );
  }
}

class SavedGridView extends StatelessWidget {
  @override
  Widget build(BuildContext context) => Center(child: Text('Saved Statuses'));
}
