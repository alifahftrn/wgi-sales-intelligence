-- phpMyAdmin SQL Dump
-- version 5.2.0
-- https://www.phpmyadmin.net/
--
-- Host: localhost:3306
-- Generation Time: Nov 25, 2026 at 07:46 AM
-- Server version: 8.0.30
-- PHP Version: 7.4.33

SET SQL_MODE = "NO_AUTO_VALUE_ON_ZERO";
START TRANSACTION;
SET time_zone = "+00:00";


/*!40101 SET @OLD_CHARACTER_SET_CLIENT=@@CHARACTER_SET_CLIENT */;
/*!40101 SET @OLD_CHARACTER_SET_RESULTS=@@CHARACTER_SET_RESULTS */;
/*!40101 SET @OLD_COLLATION_CONNECTION=@@COLLATION_CONNECTION */;
/*!40101 SET NAMES utf8mb4 */;

--
-- Database: `salesdashboard`
--

-- --------------------------------------------------------

--
-- Table structure for table `asp`
--

CREATE TABLE `asp` (
  `idASP` int NOT NULL,
  `tahun` int NOT NULL,
  `jenisTarget` varchar(20) NOT NULL COMMENT 'External atau Internal',
  `kodeDistributor` int NOT NULL,
  `dibuatOleh` int NOT NULL,
  `tanggalInput` datetime NOT NULL DEFAULT (curdate()),
  `keterangan` varchar(255) DEFAULT NULL,
  `updated_at` timestamp(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- --------------------------------------------------------

--
-- Table structure for table `asp_detail`
--

CREATE TABLE `asp_detail` (
  `idASPDetail` int NOT NULL,
  `idASP` int NOT NULL,
  `bulan` int NOT NULL,
  `kodeProduk` int NOT NULL,
  `targetPack` bigint UNSIGNED DEFAULT NULL,
  `targetLiter` decimal(16,3) DEFAULT NULL,
  `targetRupiah` decimal(18,2) DEFAULT NULL,
  `updated_at` timestamp(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
  `waktuPenetapan` datetime(6) DEFAULT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- --------------------------------------------------------

--
-- Table structure for table `delivery_order`
--

CREATE TABLE `delivery_order` (
  `idDO` int NOT NULL,
  `noDO` varchar(40) NOT NULL,
  `tanggalDO` date NOT NULL,
  `idPO` int NOT NULL,
  `statusDO` varchar(20) DEFAULT NULL,
  `keterangan` varchar(255) DEFAULT NULL,
  `updated_at` timestamp(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- --------------------------------------------------------

--
-- Table structure for table `delivery_order_detail`
--

CREATE TABLE `delivery_order_detail` (
  `idDODetail` int NOT NULL,
  `idDO` int NOT NULL,
  `nomorBaris` int NOT NULL,
  `idPODetail` int NOT NULL,
  `qtyPack` bigint UNSIGNED NOT NULL COMMENT 'ini QTY yang dikirim',
  `keterangan` varchar(255) DEFAULT NULL,
  `updated_at` timestamp(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
  `literPerPackSaatDO` decimal(12,3) DEFAULT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- --------------------------------------------------------

--
-- Table structure for table `distributor`
--

CREATE TABLE `distributor` (
  `kodeDistributor` int NOT NULL,
  `namaDistributor` varchar(120) NOT NULL,
  `area` enum('Jawa','Luar Jawa') NOT NULL,
  `region` enum('Region 1','Region 2','Region 3','Region 4','Region 5','Region 6','Region 7') NOT NULL,
  `wilayah` varchar(80) NOT NULL,
  `updated_at` timestamp(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- --------------------------------------------------------

--
-- Table structure for table `forecast`
--

CREATE TABLE `forecast` (
  `idForecast` int NOT NULL,
  `bulanForecast` date NOT NULL,
  `kodeDistributor` int NOT NULL,
  `dibuatOleh` int NOT NULL,
  `tanggalInput` datetime NOT NULL,
  `keterangan` varchar(255) DEFAULT NULL,
  `updated_at` timestamp(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- --------------------------------------------------------

--
-- Table structure for table `forecast_detail`
--

CREATE TABLE `forecast_detail` (
  `idForecastDetail` int NOT NULL,
  `idForecast` int NOT NULL,
  `kodeProduk` int NOT NULL,
  `forecastPack` bigint UNSIGNED NOT NULL,
  `forecastLiter` decimal(16,3) NOT NULL,
  `forecastRupiah` decimal(18,2) NOT NULL,
  `updated_at` timestamp(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- --------------------------------------------------------

--
-- Table structure for table `harga_produk`
--

CREATE TABLE `harga_produk` (
  `idHarga` int NOT NULL,
  `kodeProduk` int NOT NULL,
  `areaHarga` varchar(80) DEFAULT NULL,
  `berlakuMulai` date DEFAULT NULL,
  `hargaBotolSebelumPPN` decimal(18,2) DEFAULT NULL,
  `hargaBoxSebelumPPN` decimal(18,2) DEFAULT NULL,
  `hargaLiterSebelumPPN` decimal(18,4) DEFAULT NULL,
  `updated_at` timestamp(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- --------------------------------------------------------

--
-- Table structure for table `pengguna`
--

CREATE TABLE `pengguna` (
  `idPengguna` int NOT NULL,
  `namaPengguna` varchar(100) NOT NULL,
  `email` varchar(150) NOT NULL,
  `peran` varchar(30) NOT NULL,
  `password` varchar(255) NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- --------------------------------------------------------

--
-- Table structure for table `produk`
--

CREATE TABLE `produk` (
  `kodeProduk` int NOT NULL,
  `kodeAPCLama` int DEFAULT NULL,
  `namaProduk` varchar(150) NOT NULL,
  `kemasanProduk` decimal(10,3) NOT NULL,
  `isiKarton` int NOT NULL,
  `volumeTotal` decimal(12,3) NOT NULL,
  `jenisProduk` enum('2W','4W') NOT NULL,
  `brand` varchar(50) NOT NULL,
  `segment` enum('Top','Mid','Low') NOT NULL,
  `updated_at` timestamp(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- --------------------------------------------------------

--
-- Table structure for table `purchase_order`
--

CREATE TABLE `purchase_order` (
  `idPO` int NOT NULL,
  `noPO` varchar(40) NOT NULL,
  `tanggalPO` date NOT NULL,
  `kodeDistributor` int NOT NULL,
  `statusPO` varchar(20) DEFAULT NULL,
  `keterangan` varchar(255) DEFAULT NULL,
  `alasanTidakTerkirim` enum('Stock','Tonase','AR','Payment','Armada') DEFAULT NULL,
  `keteranganOutstanding` varchar(255) DEFAULT NULL,
  `updated_at` timestamp(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- --------------------------------------------------------

--
-- Table structure for table `purchase_order_detail`
--

CREATE TABLE `purchase_order_detail` (
  `idPODetail` int NOT NULL,
  `idPO` int NOT NULL,
  `kodeProduk` int NOT NULL,
  `idHarga` int NOT NULL,
  `qtyPack` bigint UNSIGNED NOT NULL,
  `updated_at` timestamp(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
  `literPerPackSaatPO` decimal(12,3) DEFAULT NULL,
  `hargaDasarPackSaatPO` decimal(18,2) DEFAULT NULL,
  `tarifPPNSaatPO` decimal(7,6) DEFAULT NULL,
  `hargaPackSetelahPPN` decimal(22,2) DEFAULT NULL,
  `qtyBatalPack` bigint UNSIGNED DEFAULT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- --------------------------------------------------------

--
-- Table structure for table `revisi_forecast`
--

CREATE TABLE `revisi_forecast` (
  `idRevisi` int NOT NULL,
  `idForecast` int NOT NULL,
  `mingguKe` int NOT NULL,
  `tanggalRevisi` datetime NOT NULL DEFAULT (curdate()),
  `dibuatOleh` int NOT NULL,
  `updated_at` timestamp(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- --------------------------------------------------------

--
-- Table structure for table `revisi_forecast_detail`
--

CREATE TABLE `revisi_forecast_detail` (
  `idRevisiDetail` int NOT NULL,
  `idRevisi` int NOT NULL,
  `kodeProduk` int NOT NULL,
  `revisiPack` bigint UNSIGNED DEFAULT NULL,
  `revisiLiter` decimal(16,3) DEFAULT NULL,
  `revisiRupiah` decimal(18,2) DEFAULT NULL,
  `updated_at` timestamp(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

--
-- Indexes for dumped tables
--

--
-- Indexes for table `asp`
--
ALTER TABLE `asp`
  ADD PRIMARY KEY (`idASP`),
  ADD KEY `kodeDistributor` (`kodeDistributor`),
  ADD KEY `dibuatOleh` (`dibuatOleh`),
  ADD KEY `idx_asp_updated_at` (`updated_at`);

--
-- Indexes for table `asp_detail`
--
ALTER TABLE `asp_detail`
  ADD PRIMARY KEY (`idASPDetail`),
  ADD KEY `idASP` (`idASP`),
  ADD KEY `kodeProduk` (`kodeProduk`),
  ADD KEY `idx_asp_detail_updated_at` (`updated_at`);

--
-- Indexes for table `delivery_order`
--
ALTER TABLE `delivery_order`
  ADD PRIMARY KEY (`idDO`),
  ADD KEY `idPO` (`idPO`),
  ADD KEY `idx_delivery_order_updated_at` (`updated_at`);

--
-- Indexes for table `delivery_order_detail`
--
ALTER TABLE `delivery_order_detail`
  ADD PRIMARY KEY (`idDODetail`),
  ADD KEY `idDO` (`idDO`),
  ADD KEY `idPODetail` (`idPODetail`),
  ADD KEY `idx_delivery_order_detail_updated_at` (`updated_at`);

--
-- Indexes for table `distributor`
--
ALTER TABLE `distributor`
  ADD PRIMARY KEY (`kodeDistributor`),
  ADD KEY `idx_distributor_updated_at` (`updated_at`);

--
-- Indexes for table `forecast`
--
ALTER TABLE `forecast`
  ADD PRIMARY KEY (`idForecast`),
  ADD KEY `kodeDistributor` (`kodeDistributor`),
  ADD KEY `dibuatOleh` (`dibuatOleh`),
  ADD KEY `idx_forecast_updated_at` (`updated_at`);

--
-- Indexes for table `forecast_detail`
--
ALTER TABLE `forecast_detail`
  ADD PRIMARY KEY (`idForecastDetail`),
  ADD KEY `idForecast` (`idForecast`),
  ADD KEY `kodeProduk` (`kodeProduk`),
  ADD KEY `idx_forecast_detail_updated_at` (`updated_at`);

--
-- Indexes for table `harga_produk`
--
ALTER TABLE `harga_produk`
  ADD PRIMARY KEY (`idHarga`),
  ADD KEY `kodeProduk` (`kodeProduk`),
  ADD KEY `idx_harga_produk_updated_at` (`updated_at`);

--
-- Indexes for table `pengguna`
--
ALTER TABLE `pengguna`
  ADD PRIMARY KEY (`idPengguna`);

--
-- Indexes for table `produk`
--
ALTER TABLE `produk`
  ADD PRIMARY KEY (`kodeProduk`),
  ADD KEY `idx_produk_updated_at` (`updated_at`);

--
-- Indexes for table `purchase_order`
--
ALTER TABLE `purchase_order`
  ADD PRIMARY KEY (`idPO`),
  ADD KEY `kodeDistributor` (`kodeDistributor`),
  ADD KEY `idx_purchase_order_updated_at` (`updated_at`);

--
-- Indexes for table `purchase_order_detail`
--
ALTER TABLE `purchase_order_detail`
  ADD PRIMARY KEY (`idPODetail`),
  ADD KEY `idPO` (`idPO`),
  ADD KEY `kodeProduk` (`kodeProduk`),
  ADD KEY `idHarga` (`idHarga`),
  ADD KEY `idx_purchase_order_detail_updated_at` (`updated_at`);

--
-- Indexes for table `revisi_forecast`
--
ALTER TABLE `revisi_forecast`
  ADD PRIMARY KEY (`idRevisi`),
  ADD KEY `idForecast` (`idForecast`),
  ADD KEY `dibuatOleh` (`dibuatOleh`),
  ADD KEY `idx_revisi_forecast_updated_at` (`updated_at`);

--
-- Indexes for table `revisi_forecast_detail`
--
ALTER TABLE `revisi_forecast_detail`
  ADD PRIMARY KEY (`idRevisiDetail`),
  ADD KEY `idRevisi` (`idRevisi`),
  ADD KEY `kodeProduk` (`kodeProduk`),
  ADD KEY `idx_revisi_forecast_detail_updated_at` (`updated_at`);

--
-- AUTO_INCREMENT for dumped tables
--

--
-- AUTO_INCREMENT for table `asp`
--
ALTER TABLE `asp`
  MODIFY `idASP` int NOT NULL AUTO_INCREMENT;

--
-- AUTO_INCREMENT for table `asp_detail`
--
ALTER TABLE `asp_detail`
  MODIFY `idASPDetail` int NOT NULL AUTO_INCREMENT;

--
-- AUTO_INCREMENT for table `delivery_order`
--
ALTER TABLE `delivery_order`
  MODIFY `idDO` int NOT NULL AUTO_INCREMENT;

--
-- AUTO_INCREMENT for table `delivery_order_detail`
--
ALTER TABLE `delivery_order_detail`
  MODIFY `idDODetail` int NOT NULL AUTO_INCREMENT;

--
-- AUTO_INCREMENT for table `forecast`
--
ALTER TABLE `forecast`
  MODIFY `idForecast` int NOT NULL AUTO_INCREMENT;

--
-- AUTO_INCREMENT for table `forecast_detail`
--
ALTER TABLE `forecast_detail`
  MODIFY `idForecastDetail` int NOT NULL AUTO_INCREMENT;

--
-- AUTO_INCREMENT for table `harga_produk`
--
ALTER TABLE `harga_produk`
  MODIFY `idHarga` int NOT NULL AUTO_INCREMENT;

--
-- AUTO_INCREMENT for table `pengguna`
--
ALTER TABLE `pengguna`
  MODIFY `idPengguna` int NOT NULL AUTO_INCREMENT;

--
-- AUTO_INCREMENT for table `purchase_order`
--
ALTER TABLE `purchase_order`
  MODIFY `idPO` int NOT NULL AUTO_INCREMENT;

--
-- AUTO_INCREMENT for table `purchase_order_detail`
--
ALTER TABLE `purchase_order_detail`
  MODIFY `idPODetail` int NOT NULL AUTO_INCREMENT;

--
-- AUTO_INCREMENT for table `revisi_forecast`
--
ALTER TABLE `revisi_forecast`
  MODIFY `idRevisi` int NOT NULL AUTO_INCREMENT;

--
-- AUTO_INCREMENT for table `revisi_forecast_detail`
--
ALTER TABLE `revisi_forecast_detail`
  MODIFY `idRevisiDetail` int NOT NULL AUTO_INCREMENT;

--
-- Constraints for dumped tables
--

--
-- Constraints for table `asp`
--
ALTER TABLE `asp`
  ADD CONSTRAINT `asp_ibfk_1` FOREIGN KEY (`kodeDistributor`) REFERENCES `distributor` (`kodeDistributor`),
  ADD CONSTRAINT `asp_ibfk_2` FOREIGN KEY (`dibuatOleh`) REFERENCES `pengguna` (`idPengguna`);

--
-- Constraints for table `asp_detail`
--
ALTER TABLE `asp_detail`
  ADD CONSTRAINT `asp_detail_ibfk_1` FOREIGN KEY (`idASP`) REFERENCES `asp` (`idASP`),
  ADD CONSTRAINT `asp_detail_ibfk_2` FOREIGN KEY (`kodeProduk`) REFERENCES `produk` (`kodeProduk`);

--
-- Constraints for table `delivery_order`
--
ALTER TABLE `delivery_order`
  ADD CONSTRAINT `delivery_order_ibfk_1` FOREIGN KEY (`idPO`) REFERENCES `purchase_order` (`idPO`);

--
-- Constraints for table `delivery_order_detail`
--
ALTER TABLE `delivery_order_detail`
  ADD CONSTRAINT `delivery_order_detail_ibfk_1` FOREIGN KEY (`idDO`) REFERENCES `delivery_order` (`idDO`),
  ADD CONSTRAINT `delivery_order_detail_ibfk_2` FOREIGN KEY (`idPODetail`) REFERENCES `purchase_order_detail` (`idPODetail`);

--
-- Constraints for table `forecast`
--
ALTER TABLE `forecast`
  ADD CONSTRAINT `forecast_ibfk_1` FOREIGN KEY (`kodeDistributor`) REFERENCES `distributor` (`kodeDistributor`),
  ADD CONSTRAINT `forecast_ibfk_2` FOREIGN KEY (`dibuatOleh`) REFERENCES `pengguna` (`idPengguna`);

--
-- Constraints for table `forecast_detail`
--
ALTER TABLE `forecast_detail`
  ADD CONSTRAINT `forecast_detail_ibfk_1` FOREIGN KEY (`idForecast`) REFERENCES `forecast` (`idForecast`),
  ADD CONSTRAINT `forecast_detail_ibfk_2` FOREIGN KEY (`kodeProduk`) REFERENCES `produk` (`kodeProduk`);

--
-- Constraints for table `harga_produk`
--
ALTER TABLE `harga_produk`
  ADD CONSTRAINT `harga_produk_ibfk_1` FOREIGN KEY (`kodeProduk`) REFERENCES `produk` (`kodeProduk`);

--
-- Constraints for table `purchase_order`
--
ALTER TABLE `purchase_order`
  ADD CONSTRAINT `purchase_order_ibfk_1` FOREIGN KEY (`kodeDistributor`) REFERENCES `distributor` (`kodeDistributor`);

--
-- Constraints for table `purchase_order_detail`
--
ALTER TABLE `purchase_order_detail`
  ADD CONSTRAINT `purchase_order_detail_ibfk_1` FOREIGN KEY (`idPO`) REFERENCES `purchase_order` (`idPO`),
  ADD CONSTRAINT `purchase_order_detail_ibfk_2` FOREIGN KEY (`kodeProduk`) REFERENCES `produk` (`kodeProduk`),
  ADD CONSTRAINT `purchase_order_detail_ibfk_3` FOREIGN KEY (`idHarga`) REFERENCES `harga_produk` (`idHarga`);

--
-- Constraints for table `revisi_forecast`
--
ALTER TABLE `revisi_forecast`
  ADD CONSTRAINT `revisi_forecast_ibfk_1` FOREIGN KEY (`idForecast`) REFERENCES `forecast` (`idForecast`),
  ADD CONSTRAINT `revisi_forecast_ibfk_2` FOREIGN KEY (`dibuatOleh`) REFERENCES `pengguna` (`idPengguna`);

--
-- Constraints for table `revisi_forecast_detail`
--
ALTER TABLE `revisi_forecast_detail`
  ADD CONSTRAINT `revisi_forecast_detail_ibfk_1` FOREIGN KEY (`idRevisi`) REFERENCES `revisi_forecast` (`idRevisi`),
  ADD CONSTRAINT `revisi_forecast_detail_ibfk_2` FOREIGN KEY (`kodeProduk`) REFERENCES `produk` (`kodeProduk`);
COMMIT;

/*!40101 SET CHARACTER_SET_CLIENT=@OLD_CHARACTER_SET_CLIENT */;
/*!40101 SET CHARACTER_SET_RESULTS=@OLD_CHARACTER_SET_RESULTS */;
/*!40101 SET COLLATION_CONNECTION=@OLD_COLLATION_CONNECTION */;
